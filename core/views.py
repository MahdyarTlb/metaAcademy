from django.views.generic import TemplateView, CreateView, ListView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.urls import reverse_lazy
from django.shortcuts import redirect
from .models import Student
from .forms import StudentForm
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from django.http import HttpResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.views.generic import ListView
from datetime import datetime

class HomeView(TemplateView):
    template_name = 'home.html'

class RegisterView(CreateView):
    model = Student
    form_class = StudentForm
    template_name = 'register.html'
    success_url = reverse_lazy('core:success')
    
    def form_valid(self, form):
        response = super().form_valid(form)
        
        self.request.session['student_name'] = form.instance.name
        self.request.session['student_age'] = form.instance.age
        self.request.session['student_phone'] = form.instance.phone_number
        self.request.session['student_reshte'] = form.instance.reshte
        self.request.session['student_school'] = form.instance.school
        self.request.session['student_city'] = form.instance.city
        self.request.session['student_moaref'] = form.instance.moaref or ''
        
        messages.success(self.request, f'✅ دانشجو  {form.instance.name} با موفقیت ثبت شد!')
        return response
    
    def form_invalid(self, form):
        messages.error(self.request, 'خطا در ثبت‌نام! لطفاً اطلاعات را بررسی کنید.')
        return super().form_invalid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'ثبت‌نام دانش‌آموز'
        return context

class StudentsView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Student
    template_name = 'students.html'
    context_object_name = 'students'
    ordering = ['-created_at']
    
    def handle_no_permission(self):
        messages.error(self.request, 'شما دسترسی به این صفحه ندارید!')
        return redirect('core:home')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_count'] = Student.objects.count()
        context['title'] = 'لیست دانش‌آموزان'
        return context
    
    def test_func(self):
        return self.request.user.is_staff
    
    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset
    
@staff_member_required
def export_excel(request):
    """
    خروجی اکسل از تمام دانش‌آموزان (همه فیلدها به صورت متن)
    """
    students = Student.objects.all().order_by('-created_at')
    
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'دانش‌آموزان'
    
    # استایل‌ها
    header_font = Font(name='B Nazanin', size=12, bold=True, color='FFFFFF')
    header_fill = PatternFill(start_color='4CAF50', end_color='4CAF50', fill_type='solid')
    header_alignment = Alignment(horizontal='center', vertical='center')
    
    cell_font = Font(name='B Nazanin', size=11)
    cell_alignment = Alignment(horizontal='center', vertical='center')
    
    border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    # هدرها
    headers = ['ردیف', 'نام و نام خانوادگی', 'سن', 'شماره تلفن', 'رشته تحصیلی', 'مدرسه', 'شهر', 'معرف', 'تاریخ ثبت']
    
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
        cell.border = border
    
    # داده‌ها (همه به صورت مستقیم)
    for row, student in enumerate(students, 2):
        ws.cell(row=row, column=1, value=row-1).border = border
        ws.cell(row=row, column=2, value=student.name).border = border
        ws.cell(row=row, column=3, value=student.age).border = border
        ws.cell(row=row, column=4, value=student.phone_number).border = border
        ws.cell(row=row, column=5, value=student.reshte).border = border  # ← مستقیم و بدون تغییر
        ws.cell(row=row, column=6, value=student.school).border = border
        ws.cell(row=row, column=7, value=student.city).border = border
        ws.cell(row=row, column=8, value=student.moaref or '').border = border
        ws.cell(row=row, column=9, value=student.created_at.strftime('%Y/%m/%d %H:%M')).border = border
        
        for col in range(1, 10):
            ws.cell(row=row, column=col).font = cell_font
            ws.cell(row=row, column=col).alignment = cell_alignment
    
    # عرض ستون‌ها
    column_widths = {
        'A': 8, 'B': 25, 'C': 10, 'D': 18, 
        'E': 25, 'F': 25, 'G': 15, 'H': 20, 'I': 20
    }
    for col, width in column_widths.items():
        ws.column_dimensions[col].width = width
    
    ws.row_dimensions[1].height = 30
    for row in range(2, len(students) + 2):
        ws.row_dimensions[row].height = 25
    
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename=students_{datetime.now().strftime("%Y%m%d_%H%M")}.xlsx'
    
    wb.save(response)
    return response

class SuccessView(TemplateView):
    template_name = 'success.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['student_name'] = self.request.session.get('student_name', '')
        context['student_age'] = self.request.session.get('student_age', '')
        context['student_phone'] = self.request.session.get('student_phone', '')
        context['student_reshte'] = self.request.session.get('student_reshte', '')
        context['student_school'] = self.request.session.get('student_school', '')
        context['student_city'] = self.request.session.get('student_city', '')
        context['student_moaref'] = self.request.session.get('student_moaref', '')
        return context