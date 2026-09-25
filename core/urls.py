from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.HomeView.as_view(), name='home'),
    path('bootcamps/', views.BootcampListView.as_view(), name='bootcamp_list'),
    path('bootcamps/<slug:slug>/', views.BootcampDetailView.as_view(), name='bootcamp_detail'),
    path('enroll/<slug:slug>/', views.EnrollView.as_view(), name='enroll'),
    path('register/', views.RegisterView.as_view(), name='register'),
    
    path('list/', views.StudentsView.as_view(), name='students'),
    path('export-excel/', views.export_excel, name='export_excel'),
    path('success/', views.SuccessView.as_view(), name='success'),
    path('import-excel/', views.import_excel, name='import_excel'),
    
    path('login/', views.CheckView.as_view(), name='check_view'),
    path('login/set-password/', views.SetPasswordView.as_view(), name='set_password'),
    path('login/login-password/', views.LoginPasswordView.as_view(), name='login_password'),
    path('logout/', views.LogoutView.as_view(), name='check_logout'),
    
    path('panel/', views.StudentDashboardView.as_view(), name='dashboard'),
    path('panel/<slug:slug>/', views.BootcampPanelView.as_view(), name='bootcamp_panel'),
    path('panel/<slug:slug>/sessions/<int:number>/', views.SessionDetailView.as_view(), name='session_detail'),
    path('panel/<slug:slug>/certificate/', views.CertificateView.as_view(), name='certificate'),
    
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('payment/', views.payment_request_view, name='payment'),
]