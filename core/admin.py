from django.contrib import admin
from .models import Student, VideoLink

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ['name', 'age', 'phone_number', 'email', 'reshte', 'city', 'created_at']
    list_filter = ['reshte', 'city', 'created_at']
    search_fields = ['name', 'phone_number', 'email', 'school', 'city']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('اطلاعات شخصی', {
            'fields': ('name', 'age', 'phone_number', 'email')
        }),
        ('اطلاعات تحصیلی', {
            'fields': ('reshte', 'school', 'city')
        }),
        ('سایر', {
            'fields': ('moaref', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(VideoLink)
class VideoLinkAdmin(admin.ModelAdmin):
    list_display = ['session_id','is_live', 'video_url', 'chat_url']
    list_display_links = ['session_id']