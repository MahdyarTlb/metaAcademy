from django.contrib import admin
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import path
from django.template.response import TemplateResponse
from .models import Student, Signature, PaymentRequest, VideoLink
from django.http import HttpResponseRedirect
from django.utils.html import format_html
from django.shortcuts import get_object_or_404
from django.urls import path, reverse

# ========== اکشن‌های سفارشی ==========

def verify_payment_and_generate_certificate(modeladmin, request, queryset):
    """
    تایید پرداخت و ساخت مدرک برای دانشجویان انتخاب شده
    """
    count = 0
    for payment in queryset:
        student = payment.student
        if not student.is_certified:
            # تایید پرداخت
            student.is_certified = True
            student.save()
            count += 1
            
            # تلاش برای ساخت مدرک (اگر امضا موجود باشد)
            try:
                from .utils import generate_certificate_for_student
                signature = Signature.objects.first()
                if signature:
                    cert_content = generate_certificate_for_student(student,)
                    student.certificate_file.save(cert_content.name, cert_content, save=True)
                    messages.success(request, f'✅ مدرک برای {student.name} ساخته شد')
            except Exception as e:
                messages.warning(request, f'⚠️ پرداخت {student.name} تایید شد ولی خطا در ساخت مدرک: {str(e)}')
    
    messages.success(request, f'{count} پرداخت با موفقیت تایید شد و مدرک‌ها ساخته شدند.')
verify_payment_and_generate_certificate.short_description = "✅ تایید پرداخت و ساخت مدرک"


def regenerate_certificate(modeladmin, request, queryset):
    """
    بازسازی مدرک برای دانشجویان انتخاب شده (بدون تغییر وضعیت پرداخت)
    """
    count = 0
    for student in queryset:
        if student.is_certified:
            try:
                from .utils import generate_certificate_for_student
                signature = Signature.objects.first()
                if signature:
                    cert_content = generate_certificate_for_student(student,)
                    student.certificate_file.save(cert_content.name, cert_content, save=True)
                    count += 1
            except Exception as e:
                messages.error(request, f'خطا برای {student.name}: {str(e)}')
    
    messages.success(request, f'{count} مدرک با موفقیت بازسازی شد.')
regenerate_certificate.short_description = "🔄 بازسازی مدرک (برای دانشجویان تایید شده)"

class CertificateClearMixin:
    """Mixin برای اضافه کردن قابلیت حذف فایل مدرک"""
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'clear-certificate/<int:student_id>/',
                self.admin_site.admin_view(self.clear_certificate),
                name='clear_certificate',
            ),
        ]
        return custom_urls + urls
    
    def clear_certificate(self, request, student_id):
        student = get_object_or_404(Student, pk=student_id)
        if student.certificate_file:
            student.certificate_file.delete(save=False)
            student.certificate_file = None
            student.save()
            self.message_user(request, f'✅ فایل مدرک {student.name} با موفقیت حذف شد.', messages.SUCCESS)
        else:
            self.message_user(request, f'ℹ️ دانشجو فایل مدرکی ندارد.', messages.INFO)
        return HttpResponseRedirect(reverse('admin:core_student_changelist'))
    
# ========== مدل Student ==========
@admin.register(Student)
class StudentAdmin(CertificateClearMixin, admin.ModelAdmin):
    list_display = [
        'name', 
        'national_code', 
        'phone_number',
        'is_certified',
        'has_certificate',
        'reshte', 
        'city', 
        'created_at'
    ]
    list_filter = ['is_certified', 'reshte', 'city', 'created_at']
    search_fields = ['name', 'national_code', 'phone_number', 'email', 'school', 'city']
    readonly_fields = ['created_at', 'updated_at', 'certificate_preview']
    actions = [regenerate_certificate]
    
    fieldsets = (
        ('اطلاعات شخصی', {
            'fields': ('name', 'age', 'national_code', 'phone_number', 'email', 'password')
        }),
        ('اطلاعات تحصیلی', {
            'fields': ('reshte', 'school', 'city')
        }),
        ('وضعیت مدرک', {
            'fields': ('is_certified', 'certificate_file', 'certificate_preview'),
            'classes': ('wide',)
        }),
        ('سایر', {
            'fields': ('moaref', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def has_certificate(self, obj):
        return bool(obj.certificate_file)
    has_certificate.boolean = True
    has_certificate.short_description = 'مدرک موجود'
    
    def certificate_preview(self, obj):
        if obj.certificate_file:
            clear_url = reverse('admin:clear_certificate', args=[obj.id])
            return format_html(
                '<a href="{}" target="_blank">🔍 مشاهده مدرک</a> | <a href="{}" style="color:#f44336;" onclick="return confirm(\'آیا از حذف کامل این فایل مطمئن هستید؟\')">🗑️ حذف</a>',
                obj.certificate_file.url,
                clear_url
            )
        return '❌ مدرکی وجود ندارد'
    certificate_preview.allow_tags = True
    certificate_preview.short_description = 'پیش‌نمایش مدرک'


# ========== مدل Signature (امضا) ==========

@admin.register(Signature)
class SignatureAdmin(admin.ModelAdmin):
    list_display = ['user', 'uploaded_at', 'signature_preview']
    readonly_fields = ['uploaded_at', 'signature_preview']
    search_fields = ['user__username', 'user__email']
    
    def signature_preview(self, obj):
        if obj.image:
            return f'<img src="{obj.image.url}" style="max-height: 60px; border: 1px solid #ddd; padding: 4px; border-radius: 4px;">'
        return '❌'
    signature_preview.allow_tags = True
    signature_preview.short_description = 'پیش‌نمایش امضا'
    
    fieldsets = (
        ('اطلاعات امضا', {
            'fields': ('user', 'image', 'signature_preview')
        }),
        ('تاریخ', {
            'fields': ('uploaded_at',),
            'classes': ('collapse',)
        }),
    )


# ========== مدل PaymentRequest ==========

@admin.register(PaymentRequest)
class PaymentRequestAdmin(admin.ModelAdmin):
    list_display = [
        'student', 
        'tracking_code', 
        'created_at', 
        'is_payment_verified',
        'has_certificate_after_payment'
    ]
    list_filter = ['created_at']
    search_fields = ['tracking_code', 'student__name', 'student__national_code']
    readonly_fields = ['student', 'tracking_code', 'created_at']
    actions = [verify_payment_and_generate_certificate]
    
    def is_payment_verified(self, obj):
        return obj.student.is_certified
    is_payment_verified.boolean = True
    is_payment_verified.short_description = 'پرداخت تایید شد؟'
    
    def has_certificate_after_payment(self, obj):
        return bool(obj.student.certificate_file)
    has_certificate_after_payment.boolean = True
    has_certificate_after_payment.short_description = 'مدرک ساخته شد؟'
    
    fieldsets = (
        ('اطلاعات درخواست', {
            'fields': ('student', 'tracking_code', 'created_at')
        }),
    )


# ========== مدل VideoLink ==========

@admin.register(VideoLink)
class VideoLinkAdmin(admin.ModelAdmin):
    list_display = ['session_id', 'is_live', 'video_url_short', 'chat_url_short']
    list_display_links = ['session_id']
    list_filter = ['is_live']
    search_fields = ['session_id', 'video_url', 'chat_url']
    list_editable = ['is_live']
    
    def video_url_short(self, obj):
        if obj.video_url:
            return f'<a href="{obj.video_url}" target="_blank">🔗 لینک ویدیو</a>'
        return '—'
    video_url_short.allow_tags = True
    video_url_short.short_description = 'ویدیو'
    
    def chat_url_short(self, obj):
        if obj.chat_url:
            return f'<a href="{obj.chat_url}" target="_blank">💬 لینک چت</a>'
        return '—'
    chat_url_short.allow_tags = True
    chat_url_short.short_description = 'چت'
    
    fieldsets = (
        ('اطلاعات جلسه', {
            'fields': ('session_id', 'is_live')
        }),
        ('لینک‌ها', {
            'fields': ('video_url', 'chat_url'),
            'description': 'لینک‌های جلسات آنلاین را در این بخش وارد کنید.'
        }),
    )


# ========== تنظیمات کلی پنل ادمین ==========

admin.site.site_header = '🎓 متا آکادمی - پنل مدیریت'
admin.site.site_title = 'مدیریت متا آکادمی'
admin.site.index_title = 'داشبورد مدیریت'