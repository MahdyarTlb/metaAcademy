from django.contrib import admin
from .models import Student

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ['name', 'age', 'phone_number', 'reshte', 'city', 'created_at']
    list_filter = ['reshte', 'city', 'created_at']
    search_fields = ['name', 'phone_number', 'school', 'city']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('اطلاعات شخصی', {
            'fields': ('name', 'age', 'phone_number')
        }),
        ('اطلاعات تحصیلی', {
            'fields': ('reshte', 'school', 'city')
        }),
        ('سایر', {
            'fields': ('moaref', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )