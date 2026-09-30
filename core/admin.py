from django.contrib import admin
from django.contrib import messages
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.db import transaction

from .models import (
    Bootcamp, Session, Student, Enrollment,
    PaymentRequest, Signature, ReferralSource,
)
from .utils import generate_certificate_for_student

from django_jalali.admin.filters import JDateFieldListFilter
from django_jalali.templatetags import jformat
import jdatetime

from django import forms
from jalali_date.fields import JalaliDateField
from jalali_date.widgets import AdminJalaliDateWidget
# ═══════════════════════════════════════════════════════
#  اکشن‌های سفارشی (روی Enrollment)
# ═══════════════════════════════════════════════════════

def verify_payment_and_issue_certificate(modeladmin, request, queryset):
    """تأیید پرداخت + صدور مدرک برای ثبت‌نام‌های انتخاب‌شده."""
    count = 0
    skipped = 0
    errors = []

    # اگه queryset از نوع PaymentRequest باشه، تبدیل کن به Enrollment
    if queryset.model.__name__ == 'PaymentRequest':
        enrollment_ids = queryset.values_list('enrollment_id', flat=True)
        queryset = Enrollment.objects.filter(pk__in=enrollment_ids)

    for enrollment in queryset.select_related('student', 'bootcamp'):
        if enrollment.is_certified and enrollment.certificate_file:
            skipped += 1
            continue
        try:
            if not enrollment.student.national_code:
                errors.append(
                    f'{enrollment.student.name} ({enrollment.bootcamp.title}): '
                    f'کد ملی ثبت نشده — کاربر باید اول فرم پرداخت رو پر کنه'
                )
                continue

            cert_content = generate_certificate_for_student(enrollment)
            if enrollment.certificate_file:
                enrollment.certificate_file.delete(save=False)
            enrollment.certificate_file.save(cert_content.name, cert_content, save=False)
            enrollment.is_certified = True
            enrollment.with_certificate = True
            enrollment.certificate_issued_at = timezone.now()
            enrollment.save(update_fields=[
                'certificate_file', 'is_certified',
                'with_certificate', 'certificate_issued_at',
            ])
            count += 1
        except Exception as e:
            errors.append(f'{enrollment.student.name} ({enrollment.bootcamp.title}): {e}')

    if count:
        messages.success(request, f'✅ مدرک برای {count} دانشجو صادر شد.')
    if skipped:
        messages.info(request, f'ℹ️ {skipped} مورد از قبل مدرک داشتند و رد شدند.')
    for err in errors:
        messages.warning(request, f'⚠️ {err}')

verify_payment_and_issue_certificate.short_description = '✅ تأیید پرداخت و صدور مدرک'


def regenerate_certificates(modeladmin, request, queryset):
    """بازسازی مدرک بدون دست‌زدن به وضعیت تأیید."""
    count = 0
    errors = []
    for enrollment in queryset.select_related('student', 'bootcamp'):
        if not enrollment.is_certified:
            continue
        try:
            cert_content = generate_certificate_for_student(enrollment)
            if enrollment.certificate_file:
                enrollment.certificate_file.delete(save=False)
            enrollment.certificate_file.save(cert_content.name, cert_content, save=False)
            enrollment.save(update_fields=['certificate_file'])
            count += 1
        except Exception as e:
            errors.append(f'{enrollment.student.name}: {e}')

    if count:
        messages.success(request, f'🔄 {count} مدرک بازسازی شد.')
    for err in errors:
        messages.error(request, f'❌ {err}')


regenerate_certificates.short_description = '🔄 بازسازی مدرک (فقط تأیید‌شده‌ها)'


def revoke_certificate(modeladmin, request, queryset):
    """لغو مدرک و حذف فایل."""
    count = 0
    for enrollment in queryset:
        if enrollment.certificate_file:
            enrollment.certificate_file.delete(save=False)
        enrollment.certificate_file = None
        enrollment.is_certified = False
        enrollment.certificate_issued_at = None
        enrollment.save(update_fields=[
            'certificate_file', 'is_certified', 'certificate_issued_at'
        ])
        count += 1
    messages.warning(request, f'🗑️ مدرک {count} مورد لغو و حذف شد.')


revoke_certificate.short_description = '🗑️ لغو مدرک و حذف فایل'

@transaction.atomic
def approve_registration_payment(modeladmin, request, queryset):
    """تأیید پرداخت ثبت‌نام + فعال‌سازی."""
    count = 0
    errors = []
    for enrollment in queryset.select_related('student', 'bootcamp'):
        if enrollment.is_active:
            continue
        try:
            bootcamp = Bootcamp.objects.select_for_update().get(pk=enrollment.bootcamp_id)
            if bootcamp.remaining_capacity is not None and bootcamp.remaining_capacity <= 0:
                errors.append(f'{enrollment.student.name} — ظرفیت {bootcamp.title} تکمیل است')
                continue

            enrollment.is_active = True
            enrollment.registration_paid_at = timezone.now()
            enrollment.save(update_fields=['is_active', 'registration_paid_at'])

            if bootcamp.remaining_capacity is not None:
                bootcamp.remaining_capacity -= 1
                bootcamp.save(update_fields=['remaining_capacity'])
            count += 1
        except Exception as e:
            errors.append(f'{enrollment.student.name}: {e}')

    if count:
        messages.success(request, f'✅ ثبت‌نام {count} نفر فعال شد.')
    for err in errors:
        messages.warning(request, f'⚠️ {err}')

approve_registration_payment.short_description = '✅ تأیید پرداخت و فعال‌سازی ثبت‌نام'

def reset_payment_submission(modeladmin, request, queryset):
    """ریست کردن کد پیگیری برای ارسال مجدد توسط کاربر."""
    count = queryset.update(
        registration_payment_submitted=False,
        registration_tracking_code=None,
    )
    messages.warning(request, f'🔄 {count} درخواست پرداخت ریست شد.')

reset_payment_submission.short_description = '🔄 ریست کد پیگیری (ارسال مجدد)'
# ═══════════════════════════════════════════════════════
#  Session (inline توی Bootcamp)
# ═══════════════════════════════════════════════════════

class SessionInlineForm(forms.ModelForm):
    date = JalaliDateField(
        label='تاریخ برگزاری',
        widget=AdminJalaliDateWidget,
        required=True,
    )

    class Meta:
        model = Session
        fields = '__all__'
        
class SessionInline(admin.TabularInline):
    model = Session
    form = SessionInlineForm
    extra = 1
    fields = [
        'number', 'title', 'session_type', 'date',
        'is_live', 'video_url', 'chat_url',
    ]
    ordering = ['number']
    show_change_link = True
    # classes = ['collapse']
    
# ═══════════════════════════════════════════════════════
#  Bootcamp
# ═══════════════════════════════════════════════════════
class BootcampAdminForm(forms.ModelForm):
    start_date = JalaliDateField(
        label='تاریخ شروع',
        widget=AdminJalaliDateWidget,
        required=False,
    )

    class Meta:
        model = Bootcamp
        fields = '__all__'
        
@admin.register(Bootcamp)
class BootcampAdmin(admin.ModelAdmin):
    form = BootcampAdminForm
    list_display = [
        'title', 'slug', 'price_display', 'certificate_fee_display', 'start_date_jalali',
        'sessions_display', 'enrollments_display',
        'capacity_display', 'is_active', 'is_registration_open', 'order',
    ]
    list_editable = ['is_active', 'is_registration_open', 'order']
    list_filter = ['is_active', 'is_registration_open', ('start_date', JDateFieldListFilter),]
    search_fields = ['title', 'slug', 'subtitle', 'summary', 'teacher']
    prepopulated_fields = {'slug': ('title',)}
    readonly_fields = ['created_at', 'remaining_capacity', 'stats_display']
    inlines = [SessionInline]
    ordering = ['order', '-created_at']

    fieldsets = (
        ('اطلاعات اصلی', {
            'fields': (
                'title', 'slug', 'subtitle', 'summary',
                'description', 'cover_image', 'teacher',
            ),
        }),
        ('زمان‌بندی', {
            'fields': ('start_date', 'duration_weeks', 'sessions_count'),
            'description': 'تعداد جلسات صرفاً یه عدد نمایشیه؛ جلسات واقعی رو توی بخش «جلسات» اضافه کن.',
        }),
        ('ثبت‌نام و ظرفیت', {
            'fields': ('price', 'capacity', 'remaining_capacity', 'is_registration_open'),
            'description': 'ظرفیت باقی‌مانده خودکار با هر ثبت‌نام کم می‌شه.',
        }),
        ('🎓 مدرک', {
            'fields': ('certificate_fee', 'certificate_template'),
            'description': (
            'صفر = مدرک رایگان (در فرم ثبت‌نام فقط گزینه‌ی «با مدرک» نمایش داده می‌شه). '
            'بیشتر از صفر = هنگام ثبت‌نام، دو گزینه «بدون مدرک» و «با مدرک» به کاربر نشون داده می‌شه.')
        }),
        ('آمار', {
            'fields': ('stats_display',),
        }),
        ('نمایش', {
            'fields': ('is_active', 'order', 'created_at'),
        }),
    )

    # ---- ستون‌های محاسباتی ----
    def price_display(self, obj):
        return 'رایگان' if obj.is_free else f'{obj.price:,} تومان'
    price_display.short_description = 'قیمت'

    def sessions_display(self, obj):
        return obj.sessions.count()
    sessions_display.short_description = 'جلسات'

    def certificate_fee_display(self, obj):
        if obj.certificate_fee == 0:
            return '🎓 رایگان'
        return f'🎓 {obj.certificate_fee:,} ت'
    certificate_fee_display.short_description = 'هزینه مدرک'

    def enrollments_display(self, obj):
        return obj.enrollments.count()
    enrollments_display.short_description = 'ثبت‌نام'

    @admin.display(description='تاریخ شروع', ordering='start_date')
    def start_date_jalali(self, obj):
        if not obj.start_date:
            return '—'
        jdate = jdatetime.date.fromgregorian(date=obj.start_date)
        return jdate.strftime('%Y/%m/%d')
    
    def capacity_display(self, obj):
        if obj.capacity is None:
            return 'نامحدود'
        remaining = obj.remaining_capacity or 0
        color = '#dc3545' if remaining <= 2 else '#10b981'
        return format_html(
            '<span style="color:{}; font-weight:700;">{}</span> / {}',
            color, remaining, obj.capacity,
        )
    capacity_display.short_description = 'ظرفیت'

    # ---- بخش آمار ----
    def stats_display(self, obj):
        if not obj.pk:
            return '—'
        total = obj.enrollments.count()
        certified = obj.enrollments.filter(is_certified=True).count()
        sessions = obj.sessions.count()
        passed = obj.sessions.filter(date__lt=timezone.now().date()).count()
        return format_html(
            '<div style="display:flex; gap:24px; flex-wrap:wrap;">'
            '  <div><strong>ثبت‌نام‌ها:</strong> {}</div>'
            '  <div><strong>مدرک صادر شده:</strong> {}</div>'
            '  <div><strong>جلسات:</strong> {} (برگزار‌شده: {})</div>'
            '</div>',
            total, certified, sessions, passed,
        )
    stats_display.short_description = 'آمار دوره'


# ═══════════════════════════════════════════════════════
#  Session
# ═══════════════════════════════════════════════════════

class SessionAdminForm(forms.ModelForm):
    date = JalaliDateField(
        label='تاریخ برگزاری',
        widget=AdminJalaliDateWidget,
        required=True,
    )

    class Meta:
        model = Session
        fields = '__all__'
        
@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    form = SessionAdminForm
    list_display = [
        'bootcamp_link', 'number', 'title', 'session_type',
        'date_jalali', 'status_display', 'is_live', 'has_video',
    ]
    list_editable = ['is_live']
    list_filter = ['bootcamp', 'session_type', 'is_live', 'date']
    search_fields = ['title', 'description', 'bootcamp__title']
    ordering = ['bootcamp', 'number']
    list_select_related = ['bootcamp']
    autocomplete_fields = ['bootcamp']
    date_hierarchy = 'date'

    fieldsets = (
        ('شناسه', {
            'fields': ('bootcamp', 'number', 'title'),
        }),
        ('برگزاری', {
            'fields': ('session_type', 'date', 'is_live', 'location'),
        }),
        ('محتوا و لینک‌ها', {
            'fields': ('video_url', 'chat_url', 'description'),
        }),
    )

    def bootcamp_link(self, obj):
        url = reverse('admin:core_bootcamp_change', args=[obj.bootcamp_id])
        return format_html('<a href="{}">{}</a>', url, obj.bootcamp.title)
    bootcamp_link.short_description = 'دوره'

    def status_display(self, obj):
        colors = {
            'passed': '#10b981',
            'today': '#f59e0b',
            'upcoming': '#6b7280',
        }
        labels = {
            'passed': '✓ برگزار شد',
            'today': '⏰ امروز',
            'upcoming': '⏳ به زودی',
        }
        return format_html(
            '<span style="color:{}; font-weight:700;">{}</span>',
            colors.get(obj.status, '#000'),
            labels.get(obj.status, obj.status),
        )
    status_display.short_description = 'وضعیت'

    def has_video(self, obj):
        return bool(obj.video_url)
    has_video.boolean = True
    has_video.short_description = 'ویدیو'
    @admin.display(description='تاریخ', ordering='date')
    
    def date_jalali(self, obj):
        if not obj.date:
            return '—'
        jdate = jdatetime.date.fromgregorian(date=obj.date)
        return jdate.strftime('%Y/%m/%d')


# ═══════════════════════════════════════════════════════
#  Enrollment
# ═══════════════════════════════════════════════════════

@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = [
        'student_link', 'bootcamp_link', 'progress_display', 'referral_source_display', 'registration_status', 'registration_tracking_code', 'certificate_choice_display'
        'is_certified', 'certificate_link', 'created_at_jalali',
    ]
    list_filter = ['is_active', 'is_certified', 'with_certificate', 'bootcamp', 'created_at']
    search_fields = [
        'student__name', 'student__phone_number', 'student__national_code',
        'bootcamp__title',
    ]
    readonly_fields = [
        'created_at', 'certificate_issued_at',
        'progress_display', 'certificate_preview',
    ]
    actions = [
        verify_payment_and_issue_certificate,
        regenerate_certificates,
        reset_payment_submission,
        revoke_certificate,
        approve_registration_payment,
    ]
    list_select_related = ['student', 'bootcamp']
    autocomplete_fields = ['student', 'bootcamp']
    date_hierarchy = 'created_at'

    fieldsets = (
        ('ثبت‌نام', {
            'fields': ('student', 'bootcamp', 'created_at'),
        }),
        ('پیشرفت', {
            'fields': ('progress_display',),
        }),
        ('مدرک', {
            'fields': (
                'is_certified', 'certificate_file',
                'certificate_issued_at', 'certificate_preview',
            ),
            'classes': ('wide',),
        }),
    )

    @admin.display(description='نوع ثبت‌نام')
    def certificate_choice_display(self, obj):
        # ─── ساخت بج اصلی ───
        if obj.is_certified:
            badge = (
                '<span style="background:rgba(16,185,129,.15); color:#047857; '
                'padding:3px 10px; border-radius:999px; font-size:12px; font-weight:700;">'
                '🎓 با مدرک (صادر شد)</span>'
            )
        elif obj.with_certificate:
            fee = obj.bootcamp.certificate_fee
            if fee > 0:
                badge = (
                    '<span style="background:rgba(245,158,11,.15); color:#b45309; '
                    'padding:3px 10px; border-radius:999px; font-size:12px; font-weight:700;">'
                    '⏳ با مدرک (در انتظار)</span>'
                )
            else:
                badge = (
                    '<span style="background:rgba(59,130,246,.15); color:#1d4ed8; '
                    'padding:3px 10px; border-radius:999px; font-size:12px; font-weight:700;">'
                    '🎓 با مدرک</span>'
                )
        else:
            badge = (
                '<span style="background:rgba(107,114,128,.12); color:#4b5563; '
                'padding:3px 10px; border-radius:999px; font-size:12px; font-weight:600;">'
                '📘 بدون مدرک</span>'
            )

        # ─── اضافه کردن کد رهگیری اگه هست ───
        if obj.tracking_code:
            return format_html(
                '{}<br><code style="font-size:11px; color:#6b7280;">{}</code>',
                mark_safe(badge),
                obj.tracking_code,
            )

        return mark_safe(badge)
        
    # ---- ستون‌ها ----
    def referral_source_display(self, obj):
        if not obj.referral_source:
            return '—'
        return format_html('<code>{}</code>', obj.referral_source.name)
    referral_source_display.short_description = 'منبع'

    def student_link(self, obj):
        url = reverse('admin:core_student_change', args=[obj.student_id])
        return format_html('<a href="{}">{}</a>', url, obj.student.name)
    student_link.short_description = 'دانشجو'
    student_link.admin_order_field = 'student__name'

    def bootcamp_link(self, obj):
        url = reverse('admin:core_bootcamp_change', args=[obj.bootcamp_id])
        return format_html('<a href="{}">{}</a>', url, obj.bootcamp.title)
    bootcamp_link.short_description = 'دوره'
    bootcamp_link.admin_order_field = 'bootcamp__title'

    def progress_display(self, obj):
        total = obj.bootcamp.sessions.count()
        if total == 0:
            return '—'
        passed = obj.passed_sessions_count
        percent = int(passed / total * 100)
        return format_html(
            '<div style="min-width:140px;">'
            '  <div style="background:#e5e7eb; border-radius:6px; height:8px; overflow:hidden;">'
            '    <div style="width:{}%; height:100%; background:linear-gradient(90deg,#fb923c,#f97316);"></div>'
            '  </div>'
            '  <small style="color:#6b7280;">{}/{} جلسه ({}%)</small>'
            '</div>',
            percent, passed, total, percent,
        )
    progress_display.short_description = 'پیشرفت'

    def certificate_link(self, obj):
        if obj.certificate_file:
            return format_html(
                '<a href="{}" target="_blank">🔍 مشاهده</a>',
                obj.certificate_file.url,
            )
        return '—'
    certificate_link.short_description = 'مدرک'

    def certificate_preview(self, obj):
        if obj.certificate_file:
            return format_html(
                '<a href="{0}" target="_blank">'
                '<img src="{0}" style="max-height:260px; border:1px solid #ddd; padding:4px; border-radius:6px;">'
                '</a>',
                obj.certificate_file.url,
            )
        return '❌ مدرکی صادر نشده'
    certificate_preview.short_description = 'پیش‌نمایش'
    
    def registration_status(self, obj):
        if obj.is_active:
            return mark_safe('<span style="color:#10b981; font-weight:700;">✅ فعال</span>')
        if obj.registration_payment_submitted:
            return mark_safe('<span style="color:#f59e0b; font-weight:700;">⏳ در انتظار تأیید</span>')
        return mark_safe('<span style="color:#dc3545; font-weight:700;">❌ پرداخت نشده</span>')
    registration_status.short_description = 'ثبت‌نام'

    def created_at_jalali(self, obj):
            if not obj.created_at:
                return '—'
            jdate = jdatetime.datetime.fromgregorian(date=obj.created_at)
            return jdate.strftime('%Y/%m/%d - %H:%M')

# ═══════════════════════════════════════════════════════
#  Student
# ═══════════════════════════════════════════════════════

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'phone_number', 'national_code',
        'enrollments_count', 'referred_by_display', 'reshte', 'city', 'created_at_jalali',
    ]
    list_filter = ['reshte', 'city', 'created_at']
    search_fields = [
        'name', 'national_code', 'phone_number',
        'email', 'school', 'city',
    ]
    readonly_fields = ['created_at', 'updated_at', 'enrollments_display']

    fieldsets = (
        ('اطلاعات شخصی', {
            'fields': ('name', 'age', 'national_code', 'phone_number', 'email', 'password'),
        }),
        ('اطلاعات تحصیلی', {
            'fields': ('reshte', 'school', 'city'),
        }),
        ('دوره‌های ثبت‌نام‌شده', {
            'fields': ('enrollments_display',),
        }),
        ('سایر', {
            'fields': ('moaref', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def referred_by_display(self, obj):
        if not obj.referred_by:
            return '—'
        return format_html('<code>{}</code>', obj.referred_by.name)
    referred_by_display.short_description = 'معرف'

    def enrollments_count(self, obj):
        return obj.enrollments.count()
    enrollments_count.short_description = 'دوره‌ها'

    def enrollments_display(self, obj):
        if not obj.pk:
            return '—'
        enrollments = obj.enrollments.select_related('bootcamp').all()
        if not enrollments:
            return 'هنوز در هیچ دوره‌ای ثبت‌نام نکرده.'
        rows = []
        for e in enrollments:
            url = reverse('admin:core_enrollment_change', args=[e.pk])
            icon = '✅' if e.is_certified else '⏳'
            rows.append(
                f'<li style="margin-bottom:6px;">'
                f'{icon} <a href="{url}">{e.bootcamp.title}</a>'
                f'</li>'
            )
        return mark_safe(
            '<ul style="margin:0; padding-right:18px;">'
            + ''.join(rows) +
            '</ul>'
        )
    enrollments_display.short_description = 'دوره‌های دانشجو'
    
    def created_at_jalali(self, obj):
        if not obj.created_at:
            return '—'
        jdate = jdatetime.datetime.fromgregorian(date=obj.created_at)
        return jdate.strftime('%Y/%m/%d - %H:%M')


# ═══════════════════════════════════════════════════════
#  PaymentRequest
# ═══════════════════════════════════════════════════════

@admin.register(PaymentRequest)
class PaymentRequestAdmin(admin.ModelAdmin):
    list_display = [
        'student_link', 'bootcamp_link', 'tracking_code',
        'created_at_jalali', 'payment_status', 'certificate_status',
    ]
    list_filter = ['created_at', 'enrollment__bootcamp']
    search_fields = [
        'tracking_code',
        'enrollment__student__name',
        'enrollment__student__national_code',
    ]
    readonly_fields = ['enrollment', 'tracking_code', 'created_at']
    actions = [verify_payment_and_issue_certificate]
    list_select_related = [
        'enrollment', 'enrollment__student', 'enrollment__bootcamp',
    ]


    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.filter(enrollment__isnull=False)

    def student_link(self, obj):
        if not obj.enrollment:
            return '—'
        url = reverse('admin:core_student_change', args=[obj.enrollment.student_id])
        return format_html('<a href="{}">{}</a>', url, obj.enrollment.student.name)
    student_link.short_description = 'دانشجو'

    def bootcamp_link(self, obj):
        if not obj.enrollment:
            return '—'
        url = reverse('admin:core_bootcamp_change', args=[obj.enrollment.bootcamp_id])
        return format_html('<a href="{}">{}</a>', url, obj.enrollment.bootcamp.title)
    bootcamp_link.short_description = 'دوره'

    def payment_status(self, obj):
        return bool(obj.enrollment and obj.enrollment.is_certified)
    payment_status.boolean = True
    payment_status.short_description = 'پرداخت تأیید؟'

    def certificate_status(self, obj):
        return bool(obj.enrollment and obj.enrollment.certificate_file)
    certificate_status.boolean = True
    certificate_status.short_description = 'مدرک؟'
    
    def created_at_jalali(self, obj):
        if not obj.created_at:
            return '—'
        jdate = jdatetime.datetime.fromgregorian(date=obj.created_at)
        return jdate.strftime('%Y/%m/%d - %H:%M')


# # ═══════════════════════════════════════════════════════
# #  Signature
# # ═══════════════════════════════════════════════════════

@admin.register(Signature)
class SignatureAdmin(admin.ModelAdmin):
    list_display = ['user', 'uploaded_at', 'signature_preview']
    readonly_fields = ['uploaded_at', 'signature_preview']
    search_fields = ['user__username', 'user__email']

    def signature_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="max-height:60px; border:1px solid #ddd; padding:4px; border-radius:4px;">',
                obj.image.url,
            )
        return '❌'
    signature_preview.short_description = 'پیش‌نمایش امضا'

@admin.register(ReferralSource)
class ReferralSourceAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'code',
        'register_link_display',
        'students_count_display',
        'enrollments_count_display',
        'created_at',
    ]
    search_fields = ['name', 'code']
    readonly_fields = [
        'links_display',
        'students_count_display',
        'enrollments_count_display',
        'created_at',
    ]

    fieldsets = (
        ('اطلاعات', {
            'fields': ('name', 'code'),
            'description': 'کد رو خودت انتخاب کن — حروف انگلیسی و خط تیره.',
        }),
        ('لینک‌ها', {
            'fields': ('links_display',),
        }),
        ('آمار', {
            'fields': ('students_count_display', 'enrollments_count_display', 'created_at'),
        }),
    )

    def register_link_display(self, obj):
        if not obj.pk:
            return '—'
        return format_html('<code>{}</code>', obj.register_link)
    register_link_display.short_description = 'لینک ثبت‌نام'

    def links_display(self, obj):
        if not obj.pk:
            return '—'

        from .models import Bootcamp
        bootcamps = Bootcamp.objects.filter(is_active=True)

        parts = []

        # لینک عمومی
        parts.append(
            f'<div style="display:flex; gap:8px; align-items:center; margin-bottom:8px;">'
            f'<strong style="min-width:120px;">لینک عمومی:</strong>'
            f'<code style="background:#f0f0f0; padding:6px 12px; border-radius:6px; '
            f'font-size:14px; flex:1;">{obj.register_link}</code>'
            f'<button type="button" onclick="navigator.clipboard.writeText(location.origin + \'{obj.register_link}\')" '
            f'style="background:#417690; color:#fff; border:none; padding:6px 14px; '
            f'border-radius:6px; cursor:pointer; font-size:13px;">📋 کپی</button>'
            f'</div>'
        )

        # لینک per bootcamp
        for b in bootcamps:
            link = obj.bootcamp_link(b.slug)
            parts.append(
                f'<div style="display:flex; gap:8px; align-items:center; margin-bottom:8px;">'
                f'<strong style="min-width:120px;">{b.title}:</strong>'
                f'<code style="background:#f0f0f0; padding:6px 12px; border-radius:6px; '
                f'font-size:14px; flex:1;">{link}</code>'
                f'<button type="button" onclick="navigator.clipboard.writeText(location.origin + \'{link}\')" '
                f'style="background:#417690; color:#fff; border:none; padding:6px 14px; '
                f'border-radius:6px; cursor:pointer; font-size:13px;">📋 کپی</button>'
                f'</div>'
            )

        return mark_safe('<div style="padding:10px 0;">' + ''.join(parts) + '</div>')
    links_display.short_description = 'لینک‌های اختصاصی'

    def students_count_display(self, obj):
        if not obj.pk:
            return '—'
        count = obj.students_count
        url = reverse('admin:core_student_changelist') + f'?referred_by__id__exact={obj.id}'
        return format_html('<a href="{}">👤 {} دانشجو</a>', url, count)
    students_count_display.short_description = 'دانشجوها'

    def enrollments_count_display(self, obj):
        if not obj.pk:
            return '—'
        count = obj.enrollments_count
        url = reverse('admin:core_enrollment_changelist') + f'?referral_source__id__exact={obj.id}'
        return format_html('<a href="{}">📚 {} ثبت‌نام</a>', url, count)
    enrollments_count_display.short_description = 'ثبت‌نام‌ها'
    
# ═══════════════════════════════════════════════════════
#  تنظیمات کلی
# ═══════════════════════════════════════════════════════

admin.site.site_header = '🎓 پارس ایکس — پنل مدیریت'
admin.site.site_title = 'مدیریت پارس ایکس'
admin.site.index_title = 'داشبورد مدیریت'