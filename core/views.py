from django.views.generic import TemplateView, CreateView, ListView, DetailView, View
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.contrib.auth.hashers import make_password, check_password
from django.utils import timezone
from django.core.validators import ValidationError
from django.urls import reverse_lazy, reverse
from django.shortcuts import redirect, render, get_object_or_404
from .models import Student, VideoLink, Signature, Bootcamp, Enrollment, Session, PaymentRequest, enroll_student
from .utils import preview_signature_on_template, generate_certificate_for_student
from .forms import StudentForm, ExcelUploadForm, CheckForm, SetPasswordForm, LoginPasswordForm, CertificateForm, PaymentForm
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from django.http import HttpResponse, Http404, request
from django.contrib.admin.views.decorators import staff_member_required
from datetime import datetime
from django.db import IntegrityError
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_exempt
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from urllib.parse import urlencode

def csrf_failure(request, reason=""):
    print("\n========== CSRF FAILURE ==========")
    print("PATH:", request.path)
    print("METHOD:", request.method)
    print("USER_AGENT:", request.META.get("HTTP_USER_AGENT"))
    print("HTTP_COOKIE:", request.META.get("HTTP_COOKIE"))
    print("COOKIES:", request.COOKIES)
    print("CSRF_COOKIE:", request.COOKIES.get("csrftoken"))
    print("REASON:", reason)
    print("==================================\n")

    from django.http import HttpResponseForbidden
    return HttpResponseForbidden("CSRF FAILED")

class HomeView(TemplateView):
    template_name = 'home.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['bootcamps'] = Bootcamp.objects.filter(is_active=True)[:6]

        student_id = self.request.session.get('auth_student_id')
        if student_id:
            try:
                student = Student.objects.get(pk=student_id)
                context['logged_in'] = True
                context['student'] = student
            except Student.DoesNotExist:
                # اگر دانشجو وجود نداشت، سشن رو پاک کن
                self.request.session.pop('auth_student_id', None)
                context['logged_in'] = False
                context['student'] = None
        else:
            context['logged_in'] = False
            context['student'] = None
            
        return context
 
class BootcampListView(ListView):
    model = Bootcamp
    template_name = 'bootcamp_list.html'
    context_object_name = 'bootcamps'

    def get_queryset(self):
        return Bootcamp.objects.filter(is_active=True)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'دوره‌ها'
        return context


class BootcampDetailView(DetailView):
    model = Bootcamp
    template_name = 'bootcamp_detail.html'
    context_object_name = 'bootcamp'
    slug_field = 'slug'
    slug_url_kwarg = 'slug'

    def get_queryset(self):
        return Bootcamp.objects.filter(is_active=True)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        student_id = self.request.session.get('auth_student_id')
        context['is_enrolled'] = bool(
            student_id and Enrollment.objects.filter(
                student_id=student_id, bootcamp=self.object
            ).exists()
        )
        context['sessions'] = self.object.sessions.all()
        return context

class RegisterView(CreateView):
    model = Student
    form_class = StudentForm
    template_name = 'register.html'

    def get_initial(self):
        initial = super().get_initial()
        next_url = self.request.GET.get('next') or self.request.session.get('next_url', '')
        if next_url:
            initial['next'] = next_url
        if phone := self.request.GET.get('phone'):
            initial['phone_number'] = phone
        if email := self.request.GET.get('email'):
            initial['email'] = email
            
        return initial

    def form_valid(self, form):
        response = super().form_valid(form)
        student = form.instance

        # ذخیره‌ی سشن برای احراز هویت
        self.request.session['auth_student_id'] = student.pk
        self.request.session['student_name'] = student.name
        self.request.session['student_age'] = student.age
        self.request.session['student_phone'] = student.phone_number
        self.request.session['student_email'] = student.email or ''
        self.request.session['student_reshte'] = student.reshte
        self.request.session['student_school'] = student.school
        self.request.session['student_city'] = student.city
        self.request.session['student_moaref'] = student.moaref or ''

        messages.success(self.request, f'✅ خوش آمدی {student.name}!')

        return response

    def form_invalid(self, form):
        existing = getattr(form, 'existing_student', None)
        if existing:
            # کاربر قبلاً ثبت‌نام کرده → بفرست به لاگین، نه پنل
            self.request.session['auth_student_id'] = existing.pk
            # ... بقیه سشن ...
            messages.warning(self.request, f'⚠️ شما قبلاً ثبت‌نام کرده‌اید. به پنل هدایت می‌شوید.')

            next_url = self.request.POST.get('next')
            if next_url:
                self.request.session['next_url'] = next_url

            return redirect('core:dashboard')

        messages.error(self.request, 'خطا در ثبت‌نام! لطفاً اطلاعات را بررسی کنید.')
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'ثبت‌نام'
        context['next'] = self.request.GET.get('next', '')
        return context
    
    def get_success_url(self):
        next_url = self.request.POST.get('next') or self.request.session.get('next_url')
        self.request.session.pop('next_url', None)
        return next_url or reverse('core:success')
 
 
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
        context['certificate_count'] = Student.objects.filter(national_code__isnull=False).count()
        context['title'] = 'لیست دانش‌آموزان'
        return context
    
    def test_func(self):
        return self.request.user.is_staff
    
    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset
 
# ==========================================================================
# پنل کاربری با ورود واقعی (شماره/ایمیل + رمز عبور)
# ==========================================================================
class CheckView(View):
    template_name = 'check.html'

    def get(self, request):
        # ← جدید: ذخیره‌ی next توی سشن تا بعد از لاگین گم نشه
        next_url = request.GET.get('next')
        if next_url:
            request.session['next_url'] = next_url

        if request.GET.get('reset'):
            request.session.pop('pending_student_id', None)

        student_id = request.session.get('auth_student_id')
        if student_id:
            student = Student.objects.filter(pk=student_id).first()
            if student:
                # ← جدید: اگه لاگین بود و next داشتیم، برو همونجا
                next_url = request.session.pop('next_url', None)
                if next_url:
                    return redirect(next_url)
                return render(request, self.template_name, {
                    'found': True, 'student': student, 'logged_in': True,
                })
            request.session.pop('auth_student_id', None)

        form = CheckForm()
        return render(request, self.template_name, {
            'form': form,
            'next': next_url or '',
        })

    def post(self, request):
        # ← جدید: نگه‌داشتن next از فرم
        next_url = request.POST.get('next') or request.session.get('next_url', '')
        if next_url:
            request.session['next_url'] = next_url

        form = CheckForm(request.POST)
        context = {'form': form, 'next': next_url}

        if form.is_valid():
            identifier = form.cleaned_data['identifier'].strip()
            is_phone = identifier.isdigit() and len(identifier) == 11
            
            try:
                if is_phone:
                    student = Student.objects.get(phone_number=identifier)
                else:
                    student = Student.objects.get(email=identifier)

                request.session['pending_student_id'] = student.pk

                if student.password:
                    return redirect('core:login_password')
                return redirect('core:set_password')

            except Student.DoesNotExist:
                # ← جدید: کاربر جدید → بفرست به ثبت‌نام با پیش‌پر کردن فیلد
                messages.info(request, 'به پارس ایکس خوش آمدید! لطفاً تکمیل ثبت‌نام کنید.')

                params = {}
                if is_phone:
                    params['phone'] = identifier
                else:
                    params['email'] = identifier
                if next_url:
                    params['next'] = next_url

                return redirect(f"{reverse('core:register')}?{urlencode(params)}")

        return render(request, self.template_name, context)

class EnrollView(View):
    """ثبت‌نام کاربر لاگین‌کرده در یک دوره."""

    def get(self, request, slug):
        bootcamp = get_object_or_404(Bootcamp, slug=slug, is_active=True)

        student_id = request.session.get('auth_student_id')
        if not student_id:
            return redirect(
                f"{reverse('core:check_view')}?next={request.get_full_path()}"
            )

        student = get_object_or_404(Student, pk=student_id)
        with_cert = request.GET.get('cert') == '1'

        try:
            enroll_student(student, bootcamp, with_certificate=with_cert)
            request.session['enrolled_bootcamp'] = bootcamp.slug
            request.session['enrolled_student_id'] = student.pk
        except ValidationError as e:
            messages.warning(request, e.message)
            return redirect(bootcamp.get_absolute_url())

        if with_cert and bootcamp.certificate_fee > 0:
            messages.info(
                request,
                'ثبت‌نام شما انجام شد. برای فعال‌سازی مدرک، اطلاعات پرداخت را وارد کنید.'
            )
            return redirect('core:certificate', slug=slug)

        messages.success(
            request,
            f'ثبت‌نام شما در «{bootcamp.title}» با موفقیت انجام شد.'
        )
        return redirect('core:bootcamp_panel', slug=slug)
    
class PendingStudentMixin:
    """کمک‌کننده برای صفحات تعیین/ورود رمز عبور که به pending_student_id نیاز دارند."""
 
    def get_pending_student(self, request):
        student_id = request.session.get('pending_student_id')
        if not student_id:
            return None
        return Student.objects.filter(pk=student_id).first()
    
class SetPasswordView(PendingStudentMixin, View):
    """تعیین رمز عبور برای اولین بار (کاربرانی که قبل از این قابلیت ثبت‌نام کرده‌اند)."""
    template_name = 'check_password.html'
 
    def get(self, request):
        student = self.get_pending_student(request)
        if not student:
            messages.warning(request, 'ابتدا شماره موبایل یا ایمیل خود را در پنل کاربری وارد کنید.')
            return redirect('core:check_view')
        if student.password:
            return redirect('core:login_password')
 
        form = SetPasswordForm()
        return render(request, self.template_name, {'form': form, 'mode': 'set', 'student': student})
 
    def post(self, request):
        student = self.get_pending_student(request)
        if not student:
            messages.warning(request, 'ابتدا شماره موبایل یا ایمیل خود را در پنل کاربری وارد کنید.')
            return redirect('core:check_view')
 
        form = SetPasswordForm(request.POST)
        if form.is_valid():
            student.password = make_password(form.cleaned_data['password1'])
            student.save(update_fields=['password'])
 
            request.session.pop('pending_student_id', None)
            request.session['auth_student_id'] = student.pk
 
            messages.success(request, '✅ رمز عبور شما با موفقیت تنظیم شد و وارد پنل شدید.')
            next_url = request.session.pop('next_url', None)
            return redirect(next_url or 'core:check_view')
 
        return render(request, self.template_name, {'form': form, 'mode': 'set', 'student': student})
    
class LoginPasswordView(PendingStudentMixin, View):
    """ورود با رمز عبور برای کاربرانی که قبلاً رمز تعیین کرده‌اند."""
    template_name = 'check_password.html'
 
    def get(self, request):
        student = self.get_pending_student(request)
        if not student:
            messages.warning(request, 'ابتدا شماره موبایل یا ایمیل خود را در پنل کاربری وارد کنید.')
            return redirect('core:check_view')
        if not student.password:
            return redirect('core:set_password')
 
        form = LoginPasswordForm()
        return render(request, self.template_name, {'form': form, 'mode': 'login', 'student': student})
 
    def post(self, request):
        student = self.get_pending_student(request)
        if not student:
            messages.warning(request, 'ابتدا شماره موبایل یا ایمیل خود را در پنل کاربری وارد کنید.')
            return redirect('core:check_view')
 
        form = LoginPasswordForm(request.POST)
        if form.is_valid():
            entered_password = form.cleaned_data['password']
            if check_password(entered_password, student.password):
                request.session.pop('pending_student_id', None)
                request.session['auth_student_id'] = student.pk
                next_url = request.session.pop('next_url', None)
                return redirect(next_url or 'core:check_view')
            form.add_error('password', 'رمز عبور اشتباه است.')
 
        return render(request, self.template_name, {'form': form, 'mode': 'login', 'student': student})
 
class LogoutView(View):
    def get(self, request):
        request.session.pop('auth_student_id', None)
        request.session.pop('pending_student_id', None)
        messages.info(request, 'از حساب کاربری خارج شدید.')
        return redirect('core:check_view')
 

class SuccessView(TemplateView):
    template_name = 'success.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        request = self.request

        # ---- اطلاعات دانشجو از سشن ----
        context['name'] = request.session.get('student_name', '')
        context['age'] = request.session.get('student_age', '')
        context['phone'] = request.session.get('student_phone', '')
        context['reshte'] = request.session.get('student_reshte', '')
        context['school'] = request.session.get('student_school', '')
        context['city'] = request.session.get('student_city', '')
        context['moaref'] = request.session.get('student_moaref', '')

        # ---- دوره‌ای که همین حالا ثبت‌نام کرده ----
        enrolled_slug = request.session.get('enrolled_bootcamp')
        enrolled_bootcamp = None
        if enrolled_slug:
            enrolled_bootcamp = Bootcamp.objects.filter(slug=enrolled_slug).first()
        context['enrolled_bootcamp'] = enrolled_bootcamp

        # ---- لیست همه‌ی دوره‌های این دانشجو ----
        student_id = request.session.get('auth_student_id')
        all_bootcamps = []
        if student_id:
            all_bootcamps = list(
                Bootcamp.objects.filter(
                    enrollments__student_id=student_id,
                    is_active=True,
                ).distinct()
            )
        context['all_bootcamps'] = all_bootcamps
        context['bootcamps_count'] = len(all_bootcamps)

        # پاک‌کردن سشن دوره، تا رفرش صفحه دوباره نشونش نده
        request.session.pop('enrolled_bootcamp', None)

        return context
    
class StudentSessionRequiredMixin:
    def dispatch(self, request, *args, **kwargs):
        if not request.session.get('auth_student_id'):
            messages.warning(
                request,
                'برای دسترسی به این صفحه ابتدا وارد پنل کاربری خود شوید.'
            )
            return redirect('core:check_view')
        return super().dispatch(request, *args, **kwargs)
 
class StudentSessionRequiredMixin:
    """چک می‌کنه دانشجو لاگین کرده."""
    def dispatch(self, request, *args, **kwargs):
        student_id = request.session.get('auth_student_id')
        if not student_id:
            return redirect(f"{reverse('core:check_view')}?next={request.path}")
        student = Student.objects.filter(pk=student_id).first()
        if not student:
            request.session.pop('auth_student_id', None)
            return redirect('core:check_view')
        request.student = student
        return super().dispatch(request, *args, **kwargs)


class EnrolledStudentRequiredMixin(StudentSessionRequiredMixin):
    """چک می‌کنه دانشجو در دوره‌ی slug ثبت‌نام کرده."""
    def dispatch(self, request, *args, **kwargs):
        # ۱. چک لاگین
        student_id = request.session.get('auth_student_id')
        if not student_id:
            return redirect(f"{reverse('core:check_view')}?next={request.path}")
        student = Student.objects.filter(pk=student_id).first()
        if not student:
            request.session.pop('auth_student_id', None)
            return redirect('core:check_view')
        request.student = student

        # ۲. چک ثبت‌نام در دوره
        slug = kwargs.get('slug')
        bootcamp = get_object_or_404(Bootcamp, slug=slug, is_active=True)
        enrollment = Enrollment.objects.filter(student=student, bootcamp=bootcamp).first()
        if not enrollment:
            messages.warning(request, 'ابتدا در این دوره ثبت‌نام کنید.')
            return redirect(bootcamp.get_absolute_url())
        request.bootcamp = bootcamp
        request.enrollment = enrollment

        return super(StudentSessionRequiredMixin, self).dispatch(request, *args, **kwargs)

class StudentDashboardView(StudentSessionRequiredMixin, TemplateView):
    template_name = 'student_dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        student = self.request.student
        enrollments = Enrollment.objects.filter(student=student).select_related('bootcamp')
        context.update({
            'student': student,
            'enrollments': enrollments,
            'enrollments_count': enrollments.count(),
            'title': 'پنل کاربری',
        })
        return context

class BootcampPanelView(EnrolledStudentRequiredMixin, TemplateView):
    template_name = 'bootcamp_panel.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        bootcamp = self.request.bootcamp
        enrollment = self.request.enrollment
        sessions = bootcamp.sessions.all()

        total = sessions.count()
        passed = enrollment.passed_sessions_count

        context.update({
            'bootcamp': bootcamp,
            'enrollment': enrollment,
            'sessions': sessions,
            'total_sessions': total,
            'progress_percent': int(passed / total * 100) if total else 0,
            'title': bootcamp.title,
        })
        return context

class SessionDetailView(EnrolledStudentRequiredMixin, TemplateView):
    template_name = 'session_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        bootcamp = self.request.bootcamp
        number = self.kwargs.get('number')
        session = get_object_or_404(Session, bootcamp=bootcamp, number=number)

        context.update({
            'session': session,
            'bootcamp': bootcamp,
            'total_sessions': bootcamp.sessions.count(),
            'title': session.title,
        })
        return context

class CertificateView(EnrolledStudentRequiredMixin, View):
    template_name = 'certificate.html'

    # ─────────── تعیین حالت ───────────
    def _build_context(self, request, form=None):
        enrollment = request.enrollment
        student = request.student
        bootcamp = request.bootcamp
        payment = getattr(enrollment, 'payment_request', None)

        base = {
            'student': student,
            'bootcamp': bootcamp,
            'enrollment': enrollment,
            'fee': bootcamp.certificate_fee,
        }

        # حالت ۱: مدرک آماده‌ی دانلود
        if enrollment.is_certified and enrollment.certificate_file:
            base.update({
                'mode': 'download',
                'certificate_url': enrollment.certificate_file.url,
            })
            return base

        # حالت ۲: درخواست پرداخت ثبت شده، در انتظار تأیید ادمین
        if enrollment.with_certificate and bootcamp.certificate_fee > 0 and payment:
            base.update({
                'mode': 'pending',
                'payment': payment,
            })
            return base

        # حالت ۳: هنوز دوره تموم نشده
        if not enrollment.is_completed:
            base.update({'mode': 'not_ready'})
            return base

        # حالت ۴: فرم تکمیل اطلاعات (+ پرداخت اگه لازمه)
        if form is None:
            form = CertificateForm(initial={
                'name': student.name,
                'national_code': student.national_code or '',
            })
        base.update({
            'mode': 'form',
            'form': form,
            'needs_payment': (
                not enrollment.with_certificate and bootcamp.certificate_fee > 0
            ),
        })
        return base

    # ─────────── GET ───────────
    def get(self, request, slug):
        return render(request, self.template_name,
                      self._build_context(request))

    # ─────────── POST ───────────
    def post(self, request, slug):
        enrollment = request.enrollment
        student = request.student
        bootcamp = request.bootcamp

        if enrollment.is_certified and enrollment.certificate_file:
            messages.error(request, '❌ مدرک این دوره قبلاً صادر شده است.')
            return redirect('core:certificate', slug=slug)

        form = CertificateForm(request.POST)

        if not form.is_valid():
            return render(request, self.template_name,
                          self._build_context(request, form=form))

        # ذخیره‌ی نام و کد ملی روی پروفایل دانشجو
        student.name = form.cleaned_data['name']
        student.national_code = form.cleaned_data['national_code']
        student.save(update_fields=['name', 'national_code'])

        # شاخه‌ی الف: کاربر بدون مدرک ثبت‌نام کرده ولی الان می‌خواد مدرک پولی
        if not enrollment.with_certificate and bootcamp.certificate_fee > 0:
            tracking = request.POST.get('tracking_code', '').strip()
            if not tracking:
                messages.error(request, 'لطفاً کد پیگیری پرداخت را وارد کنید.')
                return render(request, self.template_name,
                              self._build_context(request, form=form))

            PaymentRequest.objects.update_or_create(
                enrollment=enrollment,
                defaults={'tracking_code': tracking},
            )
            enrollment.with_certificate = True
            enrollment.save(update_fields=['with_certificate'])
            messages.success(
                request,
                '✅ اطلاعات ذخیره شد. پس از تأیید پرداخت، مدرک شما صادر می‌شود.'
            )
            return redirect('core:certificate', slug=slug)

        # شاخه‌ی ب: مدرک رایگان یا از قبل با مدرک ثبت‌نام کرده → صدور فوری
        if not enrollment.is_completed:
            messages.error(request, 'هنوز واجد شرایط دریافت مدرک نیستید.')
            return redirect('core:certificate', slug=slug)

        try:
            cert_content = generate_certificate_for_student(enrollment)
            enrollment.certificate_file.save(
                cert_content.name, cert_content, save=False
            )
            enrollment.is_certified = True
            enrollment.certificate_issued_at = timezone.now()
            enrollment.save(update_fields=[
                'certificate_file', 'is_certified', 'certificate_issued_at'
            ])
            messages.success(request, '✅ مدرک شما با موفقیت صادر شد.')
        except Exception as e:
            messages.error(request, f'خطا در ساخت مدرک: {e}')

        return redirect('core:certificate', slug=slug)
        
@login_required(login_url="/admins/admin")
def admin_dashboard(request):
    # ========== آمار ==========
    total_students = Student.objects.count()
    active_students = Student.objects.filter(national_code__isnull=False).count() + 150
    has_signature = Signature.objects.exists()
    
     # ========== پردازش آپلود امضا ==========
    if request.method == 'POST' and request.FILES.get('signature_image'):
        sig, created = Signature.objects.get_or_create(user=request.user)
        sig.image = request.FILES['signature_image']
        sig.save()
        messages.success(request, '✅ امضا با موفقیت آپلود شد')
        return redirect('core:admin_dashboard')
    
    # ========== ساخت پیشنمایش (فقط روی قالب خالی) ==========
    preview_image_url = None
    signature = Signature.objects.first()
    
    if signature:
        try:
            preview_image_url = preview_signature_on_template(
                signature.image.path,
                'static/img/certificate_template.jpg'
            )
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            print(f"خطای پیشنمایش: {error_detail}")
            messages.error(request, f'خطا در ساخت پیشنمایش: {e}')
    
    context = {
        'total_students': total_students,
        'active_students': active_students,
        'has_signature': has_signature,
        'signature': signature,
        'preview_image_url': preview_image_url,
    }
    return render(request, 'admin_dashboard.html', context)

def payment_request_view(request):
    student_id = request.session.get('auth_student_id')
    if not student_id:
        messages.error(request, 'لطفاً ابتدا وارد سیستم شوید')
        return redirect('core:check')

    try:
        student = Student.objects.get(pk=student_id)
    except Student.DoesNotExist:
        request.session.pop('auth_student_id', None)
        messages.error(request, 'کاربر یافت نشد')
        return redirect('core:check')

    # اگر قبلاً تایید شده
    if student.is_certified:
        messages.info(request, 'شما قبلاً پرداخت خود را ثبت کرده‌اید و مدرک شما فعال است.')
        return redirect('core:certificate')

    # اگر قبلاً درخواست داده ولی هنوز تایید نشده
    if hasattr(student, 'payment_request'):
        messages.warning(request, 'درخواست شما قبلاً ثبت شده و در انتظار تأیید است.')
        return redirect('core:certificate')

    if request.method == 'POST':
        form = PaymentForm(request.POST)
        
        if form.is_valid():
            payment = form.save(commit=False)
            payment.student = student
            payment.save()
            messages.success(request, '✅ درخواست شما ثبت شد. پس از تأیید واحد حسابداری، مدرک شما فعال می‌شود.')
            return redirect('core:certificate')
    else:
        form = PaymentForm()

    return render(request, 'payment.html', {
        'form': form,
        'student': student
    })
    
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
    header_font = Font(name='Bidad', size=12, bold=True, color='FFFFFF')
    header_fill = PatternFill(start_color='4CAF50', end_color='4CAF50', fill_type='solid')
    header_alignment = Alignment(horizontal='center', vertical='center')
    
    cell_font = Font(name='Bidad', size=11)
    cell_alignment = Alignment(horizontal='center', vertical='center')
    
    border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    # هدرها
    headers = ['ردیف', 'نام و نام خانوادگی', 'سن', 'شماره تلفن', 'کدملی', 'is_certified', 'رشته تحصیلی', 'مدرسه', 'شهر', 'معرف', 'تاریخ ثبت']
    
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
        ws.cell(row=row, column=5, value=student.national_code).border = border
        ws.cell(row=row, column=6, value=student.is_certified).border = border
        ws.cell(row=row, column=7, value=student.reshte).border = border
        ws.cell(row=row, column=8, value=student.school).border = border
        ws.cell(row=row, column=9, value=student.city).border = border
        ws.cell(row=row, column=10, value=student.moaref or '').border = border
        created_at_local = timezone.localtime(student.created_at)
        ws.cell(row=row, column=11, value=created_at_local.strftime('%Y/%m/%d %H:%M')).border = border
        
        for col in range(1, 12):
            ws.cell(row=row, column=col).font = cell_font
            ws.cell(row=row, column=col).alignment = cell_alignment
    
    # عرض ستون‌ها
    column_widths = {
        'A': 8, 'B': 25, 'C': 10, 'D': 18, 
        'E': 18, 'F':15, 'G': 25, 'H': 25, 'I': 15, 'J': 20, 'K': 20
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
                        elif 'کدملی' in header_str:
                            col_index['national_code'] = idx
                        elif 'is_certified' in header_str:
                            col_index['is_certified'] = idx
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
                required = ['name', 'age', 'phone', 'national_code', 'is_certified', 'reshte', 'school', 'city']
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
                        age = int(row[col_index['age']]) if row[col_index['age']] else None
                        phone_number = str(row[col_index['phone']]).strip() if row[col_index['phone']] else ''
                        national_code = str(row[col_index['national_code']]).strip() if row[col_index['national_code']] else None
                        is_certified = bool(row[col_index['is_certified']])
                        reshte = str(row[col_index['reshte']]).strip() if row[col_index['reshte']] else ''
                        school = str(row[col_index['school']]).strip() if row[col_index['school']] else ''
                        city = str(row[col_index['city']]).strip() if row[col_index['city']] else ''
                        moaref = str(row[col_index.get('moaref')]).strip() if col_index.get('moaref') and row[col_index['moaref']] else None
                        created_at_str = str(row[col_index.get('created_at')]).strip() if col_index.get('created_at') and row[col_index['created_at']] else None
                        
                        # اعتبارسنجی
                        if not name:
                            error_rows.append(f'ردیف {row_idx}: نام نمی‌تواند خالی باشد')
                            continue
                        if age is None:
                            age = 1
                        else:
                            try:
                                age = int(age)
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
                            reshte = 'ثبت نشده'
                        if not school:
                            school = 'ثبت نشده'
                        if not city:
                            city = 'ثبت نشده'
                        if is_certified == 'False':
                            is_certified = False
                        elif is_certified == 'True':
                            is_certified = True
                        
                        # ایجاد شیء دانش‌آموز
                        student = Student(
                            name=name,
                            age=age,
                            phone_number=phone_number,
                            national_code=national_code,
                            is_certified=is_certified,
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

