from django.views.generic import TemplateView, CreateView, ListView, View
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.utils import timezone
from django.core.validators import ValidationError
from django.urls import reverse_lazy, reverse
from django.shortcuts import redirect, render
from .models import Student
from .forms import StudentForm
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from django.http import HttpResponse
from django.contrib.admin.views.decorators import staff_member_required
from datetime import datetime
from .forms import ExcelUploadForm, CheckForm
from django.db import IntegrityError

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

class CheckView(View):
    template_name = 'check.html'

    def get(self, request):
        form = CheckForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = CheckForm(request.POST)
        context = {'form': form}

        if form.is_valid():
            phone = form.cleaned_data['phone']
            try:
                student = Student.objects.get(phone_number=phone)
                context['student'] = student

                request.session['student_name'] = student.name
                request.session['student_age'] = student.age
                request.session['student_phone'] = student.phone_number
                request.session['student_reshte'] = student.reshte
                request.session['student_school'] = student.school
                request.session['student_city'] = student.city
                request.session['student_moaref'] = student.moaref
                
                context['found'] = True
            except Student.DoesNotExist:
                context['found'] = False
                context['error'] = 'هیچ ثبت‌نامی با این شماره پیدا نشد، با پشتیبانی ارتباط برقرار کنید'

        return render(request, self.template_name, context)

class SuccessView(TemplateView):
    template_name = 'success.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['name'] = self.request.session.get('student_name', '')
        context['age'] = self.request.session.get('student_age', '')
        context['phone'] = self.request.session.get('student_phone', '')
        context['reshte'] = self.request.session.get('student_reshte', '')
        context['school'] = self.request.session.get('student_school', '')
        context['city'] = self.request.session.get('student_city', '')
        context['moaref'] = self.request.session.get('student_moaref', '')
        return context

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
        created_at_local = timezone.localtime(student.created_at)
        ws.cell(row=row, column=9, value=created_at_local.strftime('%Y/%m/%d %H:%M')).border = border
        
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

@staff_member_required
def import_excel(request):
    if request.method == 'POST':
        form = ExcelUploadForm(request.POST, request.FILES)
        if form.is_valid():
            excel_file = request.FILES['excel_file']
            
            if not excel_file.name.endswith(('.xlsx', '.xls')):
                messages.error(request, '❌ فرمت فایل باید .xlsx یا .xls باشد!')
                return redirect('core:import_excel')
            
            try:
                wb = openpyxl.load_workbook(excel_file)
                ws = wb.active
                
                # خواندن هدرها (ردیف اول)
                headers = [cell.value for cell in ws[1]]
                
                # پیدا کردن اندیس ستون‌ها
                col_index = {}
                for idx, header in enumerate(headers):
                    if header:
                        header_str = str(header).strip()
                        if 'نام' in header_str:
                            col_index['name'] = idx
                        elif 'سن' in header_str:
                            col_index['age'] = idx
                        elif 'تلفن' in header_str or 'شماره' in header_str:
                            col_index['phone'] = idx
                        elif 'رشته' in header_str:
                            col_index['reshte'] = idx
                        elif 'مدرسه' in header_str:
                            col_index['school'] = idx
                        elif 'شهر' in header_str:
                            col_index['city'] = idx
                        elif 'معرف' in header_str:
                            col_index['moaref'] = idx
                        elif 'تاریخ' in header_str or 'ثبت' in header_str:
                            col_index['created_at'] = idx
                
                # بررسی وجود ستون‌های ضروری
                required = ['name', 'age', 'phone', 'reshte', 'school', 'city']
                for field in required:
                    if field not in col_index:
                        messages.error(request, f'❌ ستون "{field}" در فایل پیدا نشد!')
                        return redirect('core:import_excel')
                
                added_count = 0
                error_rows = []
                
                # خواندن داده‌ها از ردیف دوم به بعد
                for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
                    if not row or not any(row):
                        continue
                    
                    try:
                        name = str(row[col_index['name']]).strip() if row[col_index['name']] else ''
                        age = int(row[col_index['age']]) if row[col_index['age']] else 0
                        phone_number = str(row[col_index['phone']]).strip() if row[col_index['phone']] else ''
                        reshte = str(row[col_index['reshte']]).strip() if row[col_index['reshte']] else ''
                        school = str(row[col_index['school']]).strip() if row[col_index['school']] else ''
                        city = str(row[col_index['city']]).strip() if row[col_index['city']] else ''
                        moaref = str(row[col_index.get('moaref')]).strip() if col_index.get('moaref') and row[col_index['moaref']] else None
                        created_at_str = str(row[col_index.get('created_at')]).strip() if col_index.get('created_at') and row[col_index['created_at']] else None
                        
                        # اعتبارسنجی
                        if not name:
                            error_rows.append(f'ردیف {row_idx}: نام نمی‌تواند خالی باشد')
                            continue
                        if age is None or age == '':
                            age = 1
                        else:
                            try:
                                age = int(age)  # تبدیل به عدد
                                if age < 1 or age > 120:
                                    error_rows.append(f'ردیف {row_idx}: سن باید بین 1 تا 120 باشد')
                                    continue
                            except (ValueError, TypeError):
                                error_rows.append(f'ردیف {row_idx}: سن باید عدد باشد')
                                continue
                        # شماره تلفن - تبدیل به رشته و استانداردسازی
                        phone_number = str(phone_number).strip() if phone_number else ''
                        # اگر با 0 شروع نمی‌شه و 10 رقمه، 0 رو اولش بذار
                        if phone_number and not phone_number.startswith('0') and len(phone_number) == 10:
                            phone_number = '0' + phone_number
                        if not phone_number or not phone_number.startswith('09') or len(phone_number) != 11:
                            error_rows.append(f'ردیف {row_idx}: شماره تلفن باید با 09 شروع شود و 11 رقم باشد')
                            continue
                        if not reshte:
                            error_rows.append(f'ردیف {row_idx}: رشته نمی‌تواند خالی باشد')
                            continue
                        if not school:
                            error_rows.append(f'ردیف {row_idx}: مدرسه نمی‌تواند خالی باشد')
                            continue
                        if not city:
                            city = 'ثبت نشده'
                        
                        # ایجاد شیء دانش‌آموز
                        student = Student(
                            name=name,
                            age=age,
                            phone_number=phone_number,
                            reshte=reshte,
                            school=school,
                            city=city,
                            moaref=moaref if moaref else None
                        )
                        try:
                            student.full_clean()
                        except ValidationError as e:
                            error_rows.append(f'ردیف {row_idx}: خطای اعتبارسنجی - {", ".join(e.messages)}')
                            continue

                        student.save()
                        
                        # اگر تاریخ ثبت در فایل وجود دارد، آن را تنظیم کن
                        if created_at_str:
                            try:
                                # تبدیل تاریخ از فرمت اکسل به datetime
                                # فرمت: 2026/07/04 23:07
                                created_at_dt = datetime.strptime(created_at_str, '%Y/%m/%d %H:%M')
                                
                                # اگر timezone فعال است، آن را aware کنید
                                if timezone.is_naive(created_at_dt):
                                    created_at_dt = timezone.make_aware(created_at_dt)
                                
                                # به‌روزرسانی فیلد created_at
                                Student.objects.filter(pk=student.pk).update(created_at=created_at_dt)
                                
                            except ValueError as e:
                                error_rows.append(f'ردیف {row_idx}: فرمت تاریخ صحیح نیست (مثال: 2026/07/04 23:07) - {str(e)}')
                        
                        added_count += 1
                        
                    except IntegrityError:
                        error_rows.append(f'ردیف {row_idx}: شماره تلفن {phone_number} تکراری است')
                    except Exception as e:
                        error_rows.append(f'ردیف {row_idx}: خطا - {str(e)}')
                
                # نمایش نتیجه
                if added_count > 0:
                    messages.success(request, f'✅ {added_count} دانش‌آموز با موفقیت اضافه شدند!')
                if error_rows:
                    for error in error_rows[:5]:
                        messages.warning(request, f'⚠️ {error}')
                    if len(error_rows) > 5:
                        messages.info(request, f'و {len(error_rows) - 5} خطای دیگر وجود دارد.')
                
                return redirect('core:students')
                
            except Exception as e:
                messages.error(request, f'❌ خطا در خواندن فایل: {str(e)}')
                return redirect('core:import_excel')
        else:
            messages.error(request, '❌ فرمت فایل صحیح نیست!')
    else:
        form = ExcelUploadForm()
    
    return render(request, 'import_excel.html', {'form': form})