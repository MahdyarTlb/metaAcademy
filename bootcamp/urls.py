from django.contrib import admin
from django.urls import path, include
from .admin import admin_site
from django.conf.urls.static import static
from django.conf import settings

urlpatterns = [
    path('admins/super', admin.site.urls),
    path('admins/admin', admin_site.urls),
    path('', include('core.urls'))
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
