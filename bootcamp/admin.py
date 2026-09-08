from django.contrib import admin
from core.models import Student, PaymentRequest
from core.admin import Student, verify_payment_and_generate_certificate
from django.utils.html import format_html

class Admins(admin.AdminSite):
    site_header = "Admin Panel"
    site_title = "پنل ادمین"

admin_site = Admins(name="myadmin")

class StudentAdmin(admin.ModelAdmin):
    list_display = ['name', 'phone_number', 'age', 'reshte', 'school', 'city', 'moaref']
    search_fields = ['name', 'phone_number', 'age', 'reshte', 'school', 'city', 'moaref']
    
    actions = None
    
    def has_delete_permission(self, request, obj=None):
        return False

class PaymentRequestAdmin(admin.ModelAdmin):
    list_display = [
        'student', 
        'tracking_code', 
        'created_at', 
        'is_payment_verified',
        'has_certificate'
    ]
    list_filter = ['created_at', 'student__is_certified']
    search_fields = ['tracking_code', 'student__name', 'student__national_code']
    readonly_fields = ['student', 'tracking_code', 'created_at', 'is_payment_verified', 'certificate_preview']
    
    actions = [verify_payment_and_generate_certificate]  # از فایل اصلی استفاده می‌کنه
    
    def is_payment_verified(self, obj):
        return obj.student.is_certified
    is_payment_verified.boolean = True
    is_payment_verified.short_description = 'وضعیت پرداخت'
    
    def has_certificate(self, obj):
        return bool(obj.student.certificate_file)
    has_certificate.boolean = True
    has_certificate.short_description = 'مدرک صادر شد؟'
    
    def certificate_preview(self, obj):
        if obj.student.certificate_file:
            return format_html(
                '<a href="{}" target="_blank">🔍 مشاهده مدرک</a>',
                obj.student.certificate_file.url
            )
        return '❌ مدرکی وجود ندارد'
    certificate_preview.allow_tags = True
    certificate_preview.short_description = 'پیش‌نمایش مدرک'
    
    def has_delete_permission(self, request, obj=None):
        return False
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False  # فقط از طریق اکشن تایید میشن
    
    fieldsets = (
        ('اطلاعات درخواست پرداخت', {
            'fields': ('student', 'tracking_code', 'created_at')
        }),
        ('وضعیت', {
            'fields': ('is_payment_verified', 'certificate_preview')
        }),
    )

admin_site.register(Student, StudentAdmin)
admin_site.register(PaymentRequest, PaymentRequestAdmin)