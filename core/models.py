from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator, EmailValidator
from django.contrib.auth.models import User
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

class VideoLink(models.Model):
    session_id = models.IntegerField(unique=True)
    video_url = models.URLField(blank=True, null=True)
    chat_url = models.URLField(blank=True, null=True, default='')
    is_live = models.BooleanField(default=True)
    
class Bootcamp(models.Model):
    title = models.CharField(
        max_length=150,
        verbose_name='عنوان دوره'
    )

    slug = models.SlugField(
        max_length=160,
        unique=True,
        verbose_name='آدرس صفحه (Slug)',
        help_text='فقط حروف انگلیسی، عدد و خط تیره. مثال: python-summer'
    )
    
    syllabus = models.TextField(blank=True, verbose_name="سرفصل‌ها")

    subtitle = models.CharField(
        max_length=250,
        blank=True,
        verbose_name='زیرعنوان کوتاه'
    )

    summary = models.TextField(
        max_length=400,
        verbose_name='توضیح کوتاه',
        help_text='برای کارت دوره در صفحه‌ی لیست دوره‌ها استفاده می‌شود.'
    )

    description = models.TextField(
        verbose_name='توضیح کامل',
        help_text='برای صفحه‌ی اختصاصی دوره استفاده می‌شود.'
    )
    
    teacher = models.CharField(
        max_length=50,
        verbose_name="نام مدرس"
    )

    cover_image = models.ImageField(
        upload_to='bootcamps/covers/',
        blank=True,
        null=True,
        verbose_name='تصویر کاور'
    )

    price = models.PositiveIntegerField(
        default=0,
        verbose_name='قیمت (تومان)',
        help_text='برای دوره‌ی رایگان، صفر بگذارید.'
    )
    
    certificate_fee = models.PositiveIntegerField(
        default=0,
        verbose_name='هزینه صدور مدرک (تومان)',
        help_text='صفر یعنی مدرک رایگان. اگه پر باشه، کاربر می‌تونه بعداً مدرک بخره.'
    )

    duration_weeks = models.PositiveSmallIntegerField(
        blank=True,
        null=True,
        verbose_name='مدت دوره (هفته)'
    )

    sessions_count = models.PositiveSmallIntegerField(
        blank=True,
        null=True,
        verbose_name='تعداد جلسات در هفته'
    )

    start_date = models.DateField(
        blank=True,
        null=True,
        verbose_name='تاریخ شروع'
    )

    capacity = models.PositiveIntegerField(
        blank=True,
        null=True,
        verbose_name='ظرفیت ثبت‌نام'
    )
    
    remaining_capacity = models.PositiveIntegerField(
        blank=True,
        null=True,
        default=capacity,
        verbose_name='ظرفیت ثبت‌نام باقیمانده'
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name='نمایش در سایت'
    )

    is_registration_open = models.BooleanField(
        default=True,
        verbose_name='ثبت‌نام باز است'
    )

    order = models.PositiveSmallIntegerField(
        default=0,
        verbose_name='ترتیب نمایش'
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='تاریخ ایجاد'
    )

    class Meta:
        verbose_name = 'بوت‌کمپ'
        verbose_name_plural = 'بوت‌کمپ‌ها'
        ordering = ['order', '-created_at']

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('core:bootcamp_detail', kwargs={'slug': self.slug})
    
    def save(self, *args, **kwargs):
            if self.remaining_capacity is None:
                self.remaining_capacity = self.capacity
            super().save(*args, **kwargs)
            
    @property
    def is_free(self):
        return self.price == 0
    
    @property
    def is_full(self):
        return self.capacity is not None and (self.remaining_capacity or 0) <= 0

    @property
    def can_register(self):
        return self.is_registration_open and not self.is_full

        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_capacity = self.capacity

    def save(self, *args, **kwargs):
        if self.remaining_capacity is None:
            self.remaining_capacity = self.capacity
        else:
            old_cap = self._original_capacity or 0
            new_cap = self.capacity or 0
            if old_cap != new_cap:
                diff = new_cap - old_cap
                self.remaining_capacity = max(0, (self.remaining_capacity or 0) + diff)

        super().save(*args, **kwargs)
        self._original_capacity = self.capacity
        
class Student(models.Model):
    name = models.CharField(
        max_length=100,
        verbose_name='نام و نام خانوادگی'
    )
    
    age = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(99)],
        verbose_name='سن',
    )
    
    is_certified = models.BooleanField(default=False)
    certificate_file = models.ImageField(upload_to='certificates/', blank=True, null=True)
        
    phone_number = models.CharField(
        max_length=11,
        validators=[
            RegexValidator(
                regex=r'^09\d{9}$',
                message='شماره تلفن صحیح نیست، حتما با اعداد انگلیسی وارد کنید.'
            )
        ],
        unique=True,
        null=True,
        blank=True,
        verbose_name='شماره تلفن'
    )
    
    national_code = models.CharField(unique=True, null=True, blank=True, verbose_name="کدملی", max_length=10)
    
    email = models.EmailField(unique=True, null=True, blank=True, verbose_name="ایمیل", validators=[EmailValidator(message='ایمیل وارد شده صحیح نیست')])
    
    password = models.CharField(
        max_length=128,
        blank=True,
        null=True,
        verbose_name='رمز عبور'
    )
    
    reshte = models.CharField(
        max_length=50,
        verbose_name='رشته تحصیلی دانشگاه/پایه مدرسه'
    )
    
    school = models.CharField(
        max_length=200,
        verbose_name='دانشگاه/مدرسه'
    )
    
    city = models.CharField(
        max_length=100,
        verbose_name='شهر'
    )
    
    moaref = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='نحوه آشنایی با بوتکمپ'
    )
    
    bootcamps = models.ManyToManyField(
        Bootcamp,
        through='Enrollment',
        related_name='students',
        blank=True,
        verbose_name='دوره‌های ثبت‌نام‌شده'
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='تاریخ ثبت'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='آخرین ویرایش'
    )
    
    class Meta:
        verbose_name = 'دانشجو'
        verbose_name_plural = 'دانشجویان'
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name

class Signature(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='signature')
    image = models.ImageField(upload_to='signatures/', verbose_name='عکس امضا')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.user.username

class PaymentRequest(models.Model):
    enrollment = models.OneToOneField(
        'Enrollment', on_delete=models.CASCADE,
        related_name='payment_request', verbose_name='ثبت‌نام', null=True, blank=True
    )
    tracking_code = models.CharField(max_length=50, verbose_name='کد پیگیری')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.enrollment.student.name} - {self.enrollment.bootcamp.title}"

class Session(models.Model):
    TYPE_CHOICES = [
        ('online', 'آنلاین'),
        ('offline', 'آفلاین'),
        ('in_person', 'حضوری'),
    ]

    bootcamp = models.ForeignKey(
        Bootcamp, on_delete=models.CASCADE,
        related_name='sessions', verbose_name='دوره'
    )
    number = models.PositiveSmallIntegerField(verbose_name='شماره جلسه')
    title = models.CharField(max_length=200, verbose_name='عنوان جلسه')
    description = models.TextField(blank=True, verbose_name='توضیحات')

    session_type = models.CharField(
        max_length=12, choices=TYPE_CHOICES,
        default='online', verbose_name='نوع جلسه'
    )
    date = models.DateField(verbose_name='تاریخ برگزاری')

    video_url = models.URLField(blank=True, null=True, verbose_name='لینک ویدیو/پخش')
    chat_url = models.URLField(blank=True, null=True, verbose_name='لینک چت')
    location = models.CharField(
        max_length=200, blank=True, verbose_name='آدرس (برای حضوری)'
    )
    is_live = models.BooleanField(default=False, verbose_name='در حال پخش زنده')

    class Meta:
        verbose_name = 'جلسه'
        verbose_name_plural = 'جلسات'
        unique_together = [('bootcamp', 'number')]
        ordering = ['number']

    def __str__(self):
        return f"{self.bootcamp.title} — جلسه {self.number}: {self.title}"

    @property
    def is_passed(self):
        """خودکار بر اساس تاریخ چک می‌شه — نیازی به cron نیست."""
        return self.date < timezone.now().date()

    @property
    def status(self):
        today = timezone.now().date()
        if self.date < today:
            return 'passed'
        if self.date == today:
            return 'today'
        return 'upcoming'

    @property
    def status_label(self):
        return {
            'passed': 'برگزار شد',
            'today': 'امروز',
            'upcoming': 'به زودی',
        }[self.status]

class Enrollment(models.Model):
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE,
        related_name='enrollments',
        verbose_name='دانشجو'
    )
    bootcamp = models.ForeignKey(
        Bootcamp, on_delete=models.CASCADE,
        related_name='enrollments',
        verbose_name='دوره'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ثبت‌نام')
    with_certificate = models.BooleanField(
        default=False, verbose_name='ثبت‌نام با مدرک'
    )
    certificate_fee_paid = models.PositiveIntegerField(
        default=0, verbose_name='هزینه‌ی پرداخت‌شده مدرک'
    )
    is_certified = models.BooleanField(default=False, verbose_name='مدرک صادر شد')
    certificate_file = models.ImageField(
        upload_to='certificates/', blank=True, null=True,
        verbose_name='فایل مدرک'
    )
    certificate_issued_at = models.DateTimeField(
        blank=True, null=True, verbose_name='تاریخ صدور'
    )
    class Meta:
        verbose_name = 'ثبت‌نام'
        verbose_name_plural = 'ثبت‌نام‌ها'
        unique_together = [('student', 'bootcamp')]   # ← جلوگیری از ثبت‌نام تکراری
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.student.name} → {self.bootcamp.title}"
    
    @property
    def is_completed(self):
        """همه‌ی جلسات دوره برگزار شده."""
        sessions = self.bootcamp.sessions.all()
        if not sessions.exists():
            return False
        return all(s.is_passed for s in sessions)

    @property
    def passed_sessions_count(self):
        return sum(1 for s in self.bootcamp.sessions.all() if s.is_passed)
    
@transaction.atomic
def enroll_student(student, bootcamp, *, with_certificate=False, silent=False):
    bootcamp = Bootcamp.objects.select_for_update().get(pk=bootcamp.pk)

    if Enrollment.objects.filter(student=student, bootcamp=bootcamp).exists():
        if silent:
            return None
        raise ValidationError('شما قبلاً در این دوره ثبت‌نام کرده‌اید.')

    if not bootcamp.can_register:
        if silent:
            return None
        raise ValidationError('ثبت‌نام این دوره بسته است.')

    enrollment = Enrollment.objects.create(student=student, bootcamp=bootcamp, with_certificate=with_certificate, certificate_fee_paid=bootcamp.certificate_fee if with_certificate else 0)

    if bootcamp.remaining_capacity is not None:
        bootcamp.remaining_capacity -= 1
        bootcamp.save(update_fields=['remaining_capacity'])

    return enrollment