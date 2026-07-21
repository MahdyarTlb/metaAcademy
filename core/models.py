from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator

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
                message='شماره تلفن باید با 09 شروع شود و 11 رقم باشد'
            )
        ],
        unique=True,
        verbose_name='شماره تلفن'
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