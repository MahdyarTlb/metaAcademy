from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator, EmailValidator
from django.contrib.auth.models import User


class Student(models.Model):
    name = models.CharField(
        max_length=100,
        verbose_name='نام و نام خانوادگی'
    )
    
    age = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(99)],
        verbose_name='سن',
    )
    
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
    
    is_certified = models.BooleanField(default=False)
    
    certificate_file = models.ImageField(upload_to='certificates/', blank=True, null=True, verbose_name='مدرک نهایی')
    
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
    student = models.OneToOneField(Student, on_delete=models.CASCADE, related_name='payment_request')
    tracking_code = models.CharField(max_length=50, verbose_name='کد پیگیری')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student.name} - {self.tracking_code}"

    
class VideoLink(models.Model):
    session_id = models.IntegerField(unique=True, verbose_name="شماره جلسه")
    video_url = models.URLField(blank=True, null=True, verbose_name="لینک ویدیو")
    chat_url = models.URLField(blank=True, null=True, verbose_name="لینک چت زنده", default='')
    is_live = models.BooleanField(default=True)
    
    def __str__(self):
        return f"جلسه {self.session_id}"