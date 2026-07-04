from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admins/admin', admin.site.urls),
    path('', include('core.urls'))
]
