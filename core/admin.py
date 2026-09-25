from django.contrib import admin
from django.contrib import messages
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from .models import (
    Bootcamp, Session, Student, Enrollment,
    PaymentRequest, Signature,
)
from .utils import generate_certificate_for_student



# ═══════════════════════════════════════════════════════
#  اکشن‌های سفارشی (روی Enrollment)
# ═══════════════════════════════════════════════════════

def verify_payment_and_issue_certificate(modeladmin, request, queryset):
    """تأیید پرداخت + صدور مدرک برای ثبت‌نام‌های انتخاب‌شده."""
    count = 0
    skipped = 0
    errors = []

    for enrollment in queryset.select_related('student', 'bootcamp'):
        if enrollment.is_certified and enrollment.certificate_file:
            skipped += 1
            continue
        try:
            cert_content = generate_certificate_for_student(enrollment)
            if enrollment.certificate_file:
                enrollment.certificate_file.delete(save=False)
            enrollment.certificate_file.save(cert_content.name, cert_content, save=False)
            enrollment.is_certified = True
            enrollment.certificate_issued_at = timezone.now()
            enrollment.save(update_fields=[
                'certificate_file', 'is_certified', 'certificate_issued_at'
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


# ═══════════════════════════════════════════════════════
#  Session (inline توی Bootcamp)
# ═══════════════════════════════════════════════════════

class SessionInline(admin.TabularInline):
    model = Session
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

@admin.register(Bootcamp)
class BootcampAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'slug', 'price_display', 'certificate_fee_display', 'start_date',
        'sessions_display', 'enrollments_display',
        'capacity_display', 'is_active', 'is_registration_open', 'order',
    ]
    list_editable = ['is_active', 'is_registration_open', 'order']
    list_filter = ['is_active', 'is_registration_open', 'start_date']
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
            'fields': ('certificate_fee',),
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

@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = [
        'bootcamp_link', 'number', 'title', 'session_type',
        'date', 'status_display', 'is_live', 'has_video',
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


# ═══════════════════════════════════════════════════════
#  Enrollment
# ═══════════════════════════════════════════════════════

@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = [
        'student_link', 'bootcamp_link', 'progress_display',
        'is_certified', 'certificate_link', 'created_at',
    ]
    list_filter = ['is_certified', 'bootcamp', 'created_at']
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
        revoke_certificate,
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

    # ---- ستون‌ها ----
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


# ═══════════════════════════════════════════════════════
#  Student
# ═══════════════════════════════════════════════════════

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'phone_number', 'national_code',
        'enrollments_count', 'reshte', 'city', 'created_at',
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


# ═══════════════════════════════════════════════════════
#  PaymentRequest
# ═══════════════════════════════════════════════════════

@admin.register(PaymentRequest)
class PaymentRequestAdmin(admin.ModelAdmin):
    list_display = [
        'student_link', 'bootcamp_link', 'tracking_code',
        'created_at', 'payment_status', 'certificate_status',
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


# ═══════════════════════════════════════════════════════
#  تنظیمات کلی
# ═══════════════════════════════════════════════════════

admin.site.site_header = '🎓 متا آکادمی — پنل مدیریت'
admin.site.site_title = 'مدیریت متا آکادمی'
admin.site.index_title = 'داشبورد مدیریت'