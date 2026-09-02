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
    
    path('check/', views.CheckView.as_view(), name='check_view'),
    path('check/set-password/', views.SetPasswordView.as_view(), name='set_password'),
    path('check/login-password/', views.LoginPasswordView.as_view(), name='login_password'),
    path('check/logout/', views.LogoutView.as_view(), name='check_logout'),
    
    path('certificate/', views.CertificateView.as_view(), name='certificate'),
    
    path('classes/offline/', views.ClassOfflineView.as_view(), name='class_offline'),
    path('classes/online/<int:session_number>/', views.ClassOnlineView.as_view(), name='class_online'),
    
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('payment/', views.payment_request_view, name='payment'),
]