from django.contrib import admin
from django.urls import path, include
from .admin import admin_site

urlpatterns = [
    path('admins/super', admin.site.urls),
    path('admins/admin', admin_site.urls),
    path('', include('core.urls'))
]
