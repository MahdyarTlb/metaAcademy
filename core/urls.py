from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.HomeView.as_view(), name='home'),
    path('register/', views.RegisterView.as_view(), name='register'),
    path('list/', views.StudentsView.as_view(), name='students'),
    path('export-excel/', views.export_excel, name='export_excel'),
    path('success/', views.SuccessView.as_view(), name='success'),
    path('import-excel/', views.import_excel, name='import_excel'),
]