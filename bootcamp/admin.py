from django.contrib import admin
from core.models import Student

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

admin_site.register(Student, StudentAdmin)