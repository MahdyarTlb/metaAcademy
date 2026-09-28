from django.views.generic import TemplateView, CreateView, ListView, DetailView, View
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.contrib.auth.hashers import make_password, check_password
from django.utils import timezone
from django.core.validators import ValidationError
from django.urls import reverse_lazy, reverse
from django.shortcuts import redirect, render, get_object_or_404
from .models import Student, VideoLink, Signature, Bootcamp, Enrollment, Session, PaymentRequest, ReferralSource, enroll_student
from .utils import preview_signature_on_template, generate_certificate_for_student
from .forms import StudentForm, ExcelUploadForm, CheckForm, SetPasswordForm, LoginPasswordForm, CertificateForm, PaymentForm, StudentProfileForm
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from django.http import HttpResponse, Http404, request
from django.contrib.admin.views.decorators import staff_member_required
from datetime import datetime
from django.db import IntegrityError, transaction
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_exempt
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from urllib.parse import urlencode
from django.db.models import Count, Q, Prefetch

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
        bootcamps = (
            Bootcamp.objects
            .filter(is_active=True)
            .order_by('order', '-created_at')
        )

        context['bootcamps'] = bootcamps
        context['bootcamps_count'] = bootcamps.count()

        context['stats'] = {
            'bootcamps': bootcamps.count(),
            'sessions': Session.objects.filter(bootcamp__in=bootcamps).count(),
            'enrollments': Enrollment.objects.filter(
                bootcamp__in=bootcamps, is_active=True
            ).count(),
            'instructors': bootcamps.exclude(teacher='')
                                    .values('teacher').distinct().count(),
        }

        context['instructors'] = list(
            bootcamps.exclude(teacher='')
                     .values_list('teacher', flat=True)
                     .distinct()
        )
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

        ref = self.request.GET.get('ref')
        if ref:
            self.request.session['ref_code'] = ref
        context['ref'] = ref or self.request.session.get('ref_code', '')
    
        student_id = self.request.session.get('auth_student_id')
        enrollment = None
        if student_id:
            enrollment = Enrollment.objects.filter(
                student_id=student_id,
                bootcamp=self.object,
            ).first()

        # is_enrolled فقط وقتی True که ثبت‌نام فعال باشه (پرداخت تأیید شده)
        context['is_enrolled'] = bool(enrollment and enrollment.is_active)

        # برای تشخیص حالت pending توی تمپلیت
        context['enrollment'] = enrollment
        context['is_pending'] = bool(enrollment and not enrollment.is_active)

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
            
        ref = self.request.GET.get('ref')
        if ref:
            self.request.session['ref_code'] = ref
            
        return initial

    def form_valid(self, form):
        response = super().form_valid(form)
        student = form.instance

        ref_code = self.request.session.get('ref_code')
        if ref_code:
            source = ReferralSource.objects.filter(code=ref_code).first()
            if source:
                student.referred_by = source
                student.save(update_fields=['referred_by'])
                
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
            # کاربر قبلاً ثبت‌نام کرده → ذخیره‌ی اطلاعات توی سشن
            self.request.session['auth_student_id'] = existing.pk
            self.request.session['student_name'] = existing.name
            self.request.session['student_age'] = existing.age
            self.request.session['student_phone'] = existing.phone_number
            self.request.session['student_email'] = existing.email or ''
            self.request.session['student_reshte'] = existing.reshte
            self.request.session['student_school'] = existing.school
            self.request.session['student_city'] = existing.city
            self.request.session['student_moaref'] = existing.moaref or ''

            messages.warning(
                self.request,
                f'⚠️ این شماره موبایل قبلاً برای {existing.name} ثبت شده است. '
                f'شما به پنل کاربری هدایت شدید.'
            )

            # اگه next داشتیم، ذخیره کن برای بعد از تأیید
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
    paginate_by = 50

    def handle_no_permission(self):
        messages.error(self.request, 'شما دسترسی به این صفحه ندارید!')
        return redirect('core:home')

    def test_func(self):
        return self.request.user.is_staff

    def get_queryset(self):
        qs = (
            Student.objects
            .prefetch_related(
                Prefetch(
                    'enrollments',
                    queryset=Enrollment.objects
                        .select_related('bootcamp')
                        .order_by('-created_at'),
                )
            )
            .annotate(
                enrollments_total=Count('enrollments', distinct=True),
                certified_total=Count(
                    'enrollments',
                    filter=Q(enrollments__is_certified=True),
                    distinct=True,
                ),
            )
            .order_by('-created_at')
        )

        # ─── فیلتر بر اساس دوره ───
        bootcamp_slug = self.request.GET.get('bootcamp')
        if bootcamp_slug:
            qs = qs.filter(enrollments__bootcamp__slug=bootcamp_slug)

        # ─── جستجو ───
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(name__icontains=q) |
                Q(phone_number__icontains=q) |
                Q(national_code__icontains=q) |
                Q(email__icontains=q) |
                Q(city__icontains=q) |
                Q(school__icontains=q)
            )

        # ─── فیلتر با/بدون مدرک ───
        cert_filter = self.request.GET.get('cert')
        if cert_filter == 'yes':
            qs = qs.filter(enrollments__is_certified=True).distinct()
        elif cert_filter == 'no':
            qs = qs.exclude(enrollments__is_certified=True).distinct()

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qs = self.get_queryset()

        # آمار کلی (روی همه‌ی دیتابیس، نه فقط فیلترشده)
        context['total_count'] = qs.count()
        context['certificate_count'] = Enrollment.objects.filter(is_certified=True).count()
        context['enrollment_count'] = Enrollment.objects.count()
        context['bootcamps_all'] = Bootcamp.objects.filter(is_active=True).order_by('order', 'title')
        context['title'] = 'لیست دانش‌آموزان'

        # فیلترهای فعلی برای حفظ در pagination و UI
        context['current_bootcamp'] = self.request.GET.get('bootcamp', '')
        context['current_q'] = self.request.GET.get('q', '')
        context['current_cert'] = self.request.GET.get('cert', '')

        return context
    
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
                return redirect('core:dashboard')
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
    
    def _attach_referral(self, request, enrollment, student):
        """منبع معرفی رو روی Enrollment و (اگه لازم بود) روی Student ست می‌کنه."""
        ref_code = request.session.pop('ref_code', None)
        if not ref_code:
            return
        
        source = ReferralSource.objects.filter(code=ref_code).first()
        if not source:
            return
        
        # روی Enrollment
        enrollment.referral_source = source
        enrollment.save(update_fields=['referral_source'])
        
        # روی Student (اگه قبلاً منبعی نداشته)
        if not student.referred_by:
            student.referred_by = source
            student.save(update_fields=['referred_by'])

    def get(self, request, slug):
        bootcamp = get_object_or_404(Bootcamp, slug=slug, is_active=True)

        # ذخیره‌ی ref توی سشن
        ref = request.GET.get('ref')
        if ref:
            request.session['ref_code'] = ref

        student_id = request.session.get('auth_student_id')
        if not student_id:
            return redirect(
                f"{reverse('core:check_view')}?next={request.get_full_path()}"
            )
        student = get_object_or_404(Student, pk=student_id)

        # اگه قبلاً Enrollment داره، همون رو چک کن
        existing = Enrollment.objects.filter(student=student, bootcamp=bootcamp).first()
        if existing:
            self._attach_referral(request, existing, student)
            if existing.is_active:
                messages.info(request, 'قبلاً در این دوره ثبت‌نام کرده‌اید.')
                return redirect('core:bootcamp_panel', slug=slug)
            return redirect('core:registration_payment', slug=slug)

        with_cert = request.GET.get('cert') == '1'

        # ─── مسیر دوره‌ی پولی ───
        if bootcamp.price > 0:
            if not bootcamp.can_register:
                messages.warning(request, 'ظرفیت این دوره تکمیل شده.')
                return redirect(bootcamp.get_absolute_url())

            enrollment = Enrollment.objects.create(
                student=student,
                bootcamp=bootcamp,
                with_certificate=with_cert,
                is_active=False,
            )
            self._attach_referral(request, enrollment, student)   # ← اینجا
            return redirect('core:registration_payment', slug=slug)

        # ─── مسیر دوره‌ی رایگان ───
        try:
            enrollment = enroll_student(student, bootcamp, with_certificate=with_cert)
            self._attach_referral(request, enrollment, student)   # ← اینجا
        except ValidationError as e:
            messages.warning(request, e.message)
            return redirect(bootcamp.get_absolute_url())

        if with_cert and bootcamp.certificate_fee > 0:
            return redirect('core:certificate_payment', slug=slug)
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
            return redirect(next_url or 'core:dashboard')
 
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
        
        if not student.password:
            return redirect('core:set_password')

        form = LoginPasswordForm(request.POST)
        if form.is_valid():
            entered_password = form.cleaned_data['password']
            if check_password(entered_password, student.password):
                request.session.pop('pending_student_id', None)
                request.session['auth_student_id'] = student.pk
                next_url = request.session.pop('next_url', None)
                return redirect(next_url or 'core:dashboard')
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
    """
    چک می‌کنه دانشجو لاگین کرده.
    - اگه لاگین نکرده → به صفحه‌ی ورود با ?next برمی‌گردونه
    - اگه لاگین کرده → request.student رو ست می‌کنه
    """

    def get_authenticated_student(self, request):
        """اگه کاربر لاگین باشه Student رو برمی‌گردونه، وگرنه None."""
        student_id = request.session.get('auth_student_id')
        if not student_id:
            return None
        student = Student.objects.filter(pk=student_id).first()
        if not student:
            request.session.pop('auth_student_id', None)
            return None
        return student

    def redirect_to_login(self, request):
        """ریدایرکت به صفحه‌ی ورود با ذخیره‌ی مسیر فعلی."""
        return redirect(f"{reverse('core:check_view')}?next={request.path}")

    def dispatch(self, request, *args, **kwargs):
        student = self.get_authenticated_student(request)
        if not student:
            return self.redirect_to_login(request)
        request.student = student
        return super().dispatch(request, *args, **kwargs)


class EnrolledStudentRequiredMixin(StudentSessionRequiredMixin):
    """
    چک می‌کنه دانشجو لاگین کرده و در دوره ثبت‌نام کرده.
    - اگه لاگین نکرده → صفحه‌ی ورود
    - اگه در دوره ثبت‌نام نکرده → صفحه‌ی دوره
    - اگه ثبت‌نام تأیید نشده و صفحه هم صفحه‌ی پرداخت نیست → صفحه‌ی پرداخت
    - وگرنه → request.bootcamp و request.enrollment رو ست می‌کنه
    """

    def dispatch(self, request, *args, **kwargs):
        # ─── مرحله ۱: چک لاگین ───
        student = self.get_authenticated_student(request)
        if not student:
            return self.redirect_to_login(request)
        request.student = student

        # ─── مرحله ۲: چک ثبت‌نام در دوره ───
        slug = kwargs.get('slug')
        if not slug:
            # این mixin فقط برای ویوهایی هست که slug دارن
            messages.error(request, 'دوره‌ای انتخاب نشده است.')
            return redirect('core:bootcamp_list')

        bootcamp = get_object_or_404(Bootcamp, slug=slug, is_active=True)
        enrollment = Enrollment.objects.filter(
            student=student, bootcamp=bootcamp
        ).first()

        if not enrollment:
            messages.warning(request, 'ابتدا در این دوره ثبت‌نام کنید.')
            return redirect(bootcamp.get_absolute_url())

        # ─── مرحله ۳: اگه پرداخت تأیید نشده → صفحه‌ی پرداخت ───
        current_url_name = (
            request.resolver_match.url_name
            if request.resolver_match else None
        )
        if not enrollment.is_active and current_url_name != 'registration_payment':
            messages.info(
                request,
                'برای دسترسی به دوره، ابتدا هزینه‌ی ثبت‌نام را پرداخت کنید.'
            )
            return redirect('core:registration_payment', slug=slug)

        # ─── مرحله ۴: ست کردن روی request ───
        request.bootcamp = bootcamp
        request.enrollment = enrollment

        # حالا dispatch اصلی (View) رو صدا می‌زنیم؛
        # چون StudentSessionRequiredMixin.dispatch دوباره لاگین چک می‌کنه،
        # این بار مستقیم میریم به والدِ والد.
        return super(StudentSessionRequiredMixin, self).dispatch(
            request, *args, **kwargs
        )

class RegistrationPaymentView(EnrolledStudentRequiredMixin, View):
    template_name = 'registration_payment.html'

    def get(self, request, slug):
        enrollment = request.enrollment
        bootcamp = request.bootcamp

        # ثبت‌نام فعال → پنل
        if enrollment.is_active:
            messages.info(request, 'ثبت‌نام شما قبلاً تأیید شده است.')
            return redirect('core:bootcamp_panel', slug=slug)

        # قبلاً کد فرستاده → برگرد به صفحه‌ی دوره
        if enrollment.registration_payment_submitted:
            messages.info(
                request,
                'درخواست پرداخت شما قبلاً ثبت شده و در انتظار تأیید است.'
            )
            return redirect(bootcamp.get_absolute_url())

        # فرم
        return render(request, self.template_name, {
            'bootcamp': bootcamp,
            'student': request.student,
            'enrollment': enrollment,
            'price': bootcamp.price,
        })

    def post(self, request, slug):
        enrollment = request.enrollment
        bootcamp = request.bootcamp

        # گارد: قبلاً فرستاده
        if enrollment.registration_payment_submitted:
            messages.warning(
                request,
                'کد پیگیری قبلاً ثبت شده. منتظر تأیید پشتیبانی باشید.'
            )
            return redirect(bootcamp.get_absolute_url())

        # گارد: قبلاً تأیید شده
        if enrollment.is_active:
            return redirect('core:bootcamp_panel', slug=slug)

        tracking = request.POST.get('tracking_code', '').strip()
        if not tracking or len(tracking) < 4:
            messages.error(request, 'کد پیگیری معتبر وارد کنید.')
            return redirect('core:registration_payment', slug=slug)

        # ─── ذخیره ───
        enrollment.registration_tracking_code = tracking
        enrollment.registration_payment_submitted = True
        enrollment.save(update_fields=[
            'registration_tracking_code',
            'registration_payment_submitted',
        ])

        messages.success(
            request,
            '✅ درخواست پرداخت ثبت شد. پس از تأیید پشتیبانی، ثبت‌نام فعال می‌شود.'
        )
        return redirect(bootcamp.get_absolute_url())
    
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

    def _build_context(self, request, form=None):
        enrollment = request.enrollment
        student = request.student
        bootcamp = request.bootcamp
        fee = bootcamp.certificate_fee
        payment = PaymentRequest.objects.filter(enrollment=enrollment).first()

        base = {
            'student': student,
            'bootcamp': bootcamp,
            'enrollment': enrollment,
            'fee': fee,
        }

        # حالت ۱: مدرک آمادهی دانلود
        if enrollment.is_certified and enrollment.certificate_file:
            base.update({
                'mode': 'download',
                'certificate_url': enrollment.certificate_file.url,
            })
            return base

        # حالت ۲: در انتظار تأیید پرداخت
        if fee > 0 and payment:
            base.update({'mode': 'pending', 'payment': payment})
            return base

        # حالت ۳: هنوز دوره تموم نشده
        if not enrollment.is_completed:
            base.update({'mode': 'not_ready'})
            return base

        # حالت ۴: پولی و کاربر با مدرک ثبتنام نکرده → دکمهی فعالسازی
        if fee > 0 and not enrollment.with_certificate:
            base.update({'mode': 'activate_cert'})
            return base

        # حالت ۵: رایگان → فرم نام + کد ملی
        if form is None:
            form = CertificateForm(initial={
                'name': student.name,
                'national_code': student.national_code or '',
            })
        base.update({'mode': 'form', 'form': form})
        return base

    def get(self, request, slug):
        enrollment = request.enrollment
        bootcamp = request.bootcamp
        fee = bootcamp.certificate_fee
        payment = PaymentRequest.objects.filter(enrollment=enrollment).exists()

        # اگه پولی و کاربر با مدرک ثبتنام کرده و پرداخت ثبت نشده → برو صفحهی پرداخت
        if fee > 0 and enrollment.with_certificate and not payment and not enrollment.is_certified:
            return redirect('core:certificate_payment', slug=slug)

        return render(request, self.template_name, self._build_context(request))

    def post(self, request, slug):
        enrollment = request.enrollment
        student = request.student
        bootcamp = request.bootcamp
        fee = bootcamp.certificate_fee

        if enrollment.is_certified and enrollment.certificate_file:
            messages.error(request, '❌ مدرک این دوره قبلاً صادر شده است.')
            return redirect('core:certificate', slug=slug)

        # ─── گارد: اگه پولی و پرداخت تأیید نشده، مدرک صادر نکن ───
        if fee > 0:
            messages.error(
                request,
                'برای صدور این مدرک، ابتدا هزینه را پرداخت و تأیید کنید.'
            )
            return redirect('core:certificate', slug=slug)

        # ─── فقط مدرک رایگان ───
        form = CertificateForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name,
                          self._build_context(request, form=form))

        student.name = form.cleaned_data['name']
        student.national_code = form.cleaned_data['national_code']
        student.save(update_fields=['name', 'national_code'])

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
            enrollment.with_certificate = True
            enrollment.save(update_fields=[
                'certificate_file', 'is_certified',
                'certificate_issued_at', 'with_certificate',
            ])
            messages.success(request, '✅ مدرک شما با موفقیت صادر شد.')
        except Exception as e:
            messages.error(request, f'خطا در ساخت مدرک: {e}')

        return redirect('core:certificate', slug=slug)

class CertificatePaymentView(EnrolledStudentRequiredMixin, View):
    """صفحهی جدا برای پرداخت هزینهی مدرک + ثبت اطلاعات چاپ روی مدرک."""

    template_name = 'certificate_payment.html'

    def get(self, request, slug):
        enrollment = request.enrollment
        student = request.student
        bootcamp = request.bootcamp

        # اگه مدرک صادر شده، برو صفحهی مدرک
        if enrollment.is_certified and enrollment.certificate_file:
            return redirect('core:certificate', slug=slug)

        # اگه پرداخت قبلاً ثبت شده، برو صفحهی مدرک (pending)
        if PaymentRequest.objects.filter(enrollment=enrollment).exists():
            return redirect('core:certificate', slug=slug)

        form = CertificateForm(initial={
            'name': student.name,
            'national_code': student.national_code or '',
        })

        return render(request, self.template_name, {
            'form': form,
            'student': student,
            'bootcamp': bootcamp,
            'enrollment': enrollment,
            'fee': bootcamp.certificate_fee,
        })

    def post(self, request, slug):
        enrollment = request.enrollment
        student = request.student
        bootcamp = request.bootcamp

        form = CertificateForm(request.POST)
        tracking = request.POST.get('tracking_code', '').strip()

        if not form.is_valid():
            return render(request, self.template_name, {
                'form': form, 'student': student,
                'bootcamp': bootcamp, 'enrollment': enrollment,
                'fee': bootcamp.certificate_fee,
            })

        if not tracking:
            messages.error(request, 'کد پیگیری پرداخت را وارد کنید.')
            return render(request, self.template_name, {
                'form': form, 'student': student,
                'bootcamp': bootcamp, 'enrollment': enrollment,
                'fee': bootcamp.certificate_fee,
            })

        # ذخیرهی نام و کد ملی روی پروفایل
        student.name = form.cleaned_data['name']
        student.national_code = form.cleaned_data['national_code']
        student.save(update_fields=['name', 'national_code'])

        # ساخت درخواست پرداخت
        PaymentRequest.objects.update_or_create(
            enrollment=enrollment,
            defaults={'tracking_code': tracking},
        )

        messages.success(
            request,
            '✅ درخواست پرداخت شما ثبت شد. پس از تأیید توسط پشتیبانی، مدرک صادر میشود.'
        )
        return redirect('core:certificate', slug=slug)

class ProfileEditView(StudentSessionRequiredMixin, View):
    template_name = 'profile_edit.html'

    def get(self, request):
        form = StudentProfileForm(instance=request.student)
        return render(request, self.template_name, {
            'form': form,
            'student': request.student,
            'title': 'ویرایش پروفایل',
        })

    def post(self, request):
        form = StudentProfileForm(request.POST, instance=request.student)
        if form.is_valid():
            form.save()
            # آپدیت سشن‌ها برای هماهنگی
            request.session['student_name'] = request.student.name
            request.session['student_age'] = request.student.age
            request.session['student_email'] = request.student.email or ''
            request.session['student_reshte'] = request.student.reshte
            request.session['student_school'] = request.student.school
            request.session['student_city'] = request.student.city
            request.session['student_moaref'] = request.student.moaref or ''

            messages.success(request, '✅ اطلاعات پروفایل با موفقیت به‌روزرسانی شد.')
            return redirect('core:dashboard')

        messages.error(request, 'لطفاً خطاهای فرم را برطرف کنید.')
        return render(request, self.template_name, {
            'form': form,
            'student': request.student,
            'title': 'ویرایش پروفایل',
        })
        
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
    """خروجی اکسل از همه‌ی ثبت‌نام‌ها (per Enrollment)."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

    enrollments = (
        Enrollment.objects
        .select_related('student', 'bootcamp', 'student__referred_by')
        .order_by('-created_at')
    )

    wb = Workbook()
    ws = wb.active
    ws.title = 'ثبت‌نام‌ها'

    # استایل‌ها
    header_font = Font(name='Bidad', size=12, bold=True, color='FFFFFF')
    header_fill = PatternFill(start_color='4CAF50', end_color='4CAF50', fill_type='solid')
    header_align = Alignment(horizontal='center', vertical='center')
    cell_font = Font(name='Bidad', size=11)
    cell_align = Alignment(horizontal='center', vertical='center')
    border = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin'),
    )

    headers = [
        'ردیف', 'نام و نام خانوادگی', 'سن', 'شماره تلفن', 'کدملی', 'ایمیل',
        'دوره', 'با مدرک', 'مدرک صادر شده',
        'رشته تحصیلی', 'مدرسه', 'شهر', 'معرف', 'کد معرف', 'تاریخ ثبت',
    ]

    for c, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=c, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align
        cell.border = border

    for row, e in enumerate(enrollments, 2):
        s = e.student
        ref_code = s.referred_by.code if s.referred_by else ''
        created_local = timezone.localtime(e.created_at)

        values = [
            row - 1,
            s.name,
            s.age,
            s.phone_number,
            s.national_code or '',
            s.email or '',
            e.bootcamp.slug,
            'بله' if e.with_certificate else 'خیر',
            'بله' if e.is_certified else 'خیر',
            s.reshte,
            s.school,
            s.city,
            s.moaref or '',
            ref_code,
            created_local.strftime('%Y/%m/%d %H:%M'),
        ]

        for c, val in enumerate(values, 1):
            cell = ws.cell(row=row, column=c, value=val)
            cell.font = cell_font
            cell.alignment = cell_align
            cell.border = border

    # عرض ستون‌ها
    widths = {
        'A': 8, 'B': 25, 'C': 8, 'D': 16, 'E': 14, 'F': 22,
        'G': 18, 'H': 10, 'I': 14, 'J': 22, 'K': 22,
        'L': 14, 'M': 18, 'N': 14, 'O': 20,
    }
    for c, w in widths.items():
        ws.column_dimensions[c].width = w
    ws.row_dimensions[1].height = 30

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = (
        f'attachment; filename=enrollments_{datetime.now().strftime("%Y%m%d_%H%M")}.xlsx'
    )
    wb.save(response)
    return response

@staff_member_required
def import_excel(request):
    if request.method != 'POST':
        return render(request, 'import_excel.html', {'form': ExcelUploadForm()})

    form = ExcelUploadForm(request.POST, request.FILES)
    if not form.is_valid():
        messages.error(request, '❌ فرمت فایل صحیح نیست!')
        return render(request, 'import_excel.html', {'form': form})

    excel_file = request.FILES['excel_file']
    if not excel_file.name.endswith(('.xlsx', '.xls')):
        messages.error(request, '❌ فرمت فایل باید .xlsx یا .xls باشد!')
        return redirect('core:import_excel')

    try:
        wb = openpyxl.load_workbook(excel_file, data_only=True)
        ws = wb.active

        # ─── تشخیص هدرها ───
        headers = [str(cell.value).strip() if cell.value else '' for cell in ws[1]]

        col = {}
        for idx, h in enumerate(headers):
            if 'نام' in h and 'نام' not in col:
                col['name'] = idx
            elif h == 'سن' or 'سن' in h:
                col['age'] = idx
            elif 'تلفن' in h or 'شماره' in h and 'شماره' not in col.get('phone_used', ''):
                col.setdefault('phone', idx)
            elif 'کدملی' in h or 'کد ملی' in h:
                col['national_code'] = idx
            elif 'is_certified' in h or 'مدرک' in h and 'certified' not in col.get('cert_used', ''):
                col.setdefault('is_certified', idx)
            elif 'رشته' in h:
                col['reshte'] = idx
            elif 'مدرسه' in h or 'دانشگاه' in h:
                col['school'] = idx
            elif 'شهر' in h:
                col['city'] = idx
            elif 'معرف' in h and 'کد' not in h:
                col['moaref'] = idx
            elif 'تاریخ' in h or 'ثبت' in h:
                col['created_at'] = idx
            elif 'دوره' in h or 'bootcamp' in h.lower():
                col['bootcamp'] = idx
            elif 'با مدرک' in h:
                col['with_certificate'] = idx
            elif 'کد معرف' in h or 'referral' in h.lower():
                col['referral_code'] = idx

        # ─── چک ستون‌های ضروری ───
        required = ['name', 'phone']
        for f in required:
            if f not in col:
                messages.error(request, f'❌ ستون "{f}" در فایل پیدا نشد!')
                return redirect('core:import_excel')

        # ─── تشخیص حالت: قدیمی یا جدید؟ ───
        is_legacy = 'bootcamp' not in col
        default_bootcamp_slug = 'python-basic'

        if is_legacy:
            default_bootcamp = Bootcamp.objects.filter(slug=default_bootcamp_slug).first()
            if not default_bootcamp:
                messages.error(
                    request,
                    f'❌ بوت‌کمپ "{default_bootcamp_slug}" پیدا نشد. '
                    f'اول اون رو بساز، بعد اکسل رو آپلود کن.'
                )
                return redirect('core:import_excel')
            messages.info(
                request,
                f'📋 فایل قدیمی تشخیص داده شد — همه‌ی کاربران به «{default_bootcamp.title}» منتقل می‌شن.'
            )

        added_students = 0
        updated_students = 0
        added_enrollments = 0
        errors = []

        def cell_value(row, key):
            if key not in col:
                return None
            idx = col[key]
            val = row[idx] if idx < len(row) else None
            if val is None:
                return None
            return str(val).strip() if isinstance(val, str) else val

        with transaction.atomic():
            for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
                if not row or not any(row):
                    continue

                try:
                    # ─── اطلاعات پایه ───
                    name = cell_value(row, 'name') or ''
                    phone = cell_value(row, 'phone') or ''
                    phone = str(phone).strip()

                    if not name:
                        errors.append(f'ردیف {row_idx}: نام خالی')
                        continue

                    # ─── استانداردسازی شماره ───
                    if phone and not phone.startswith('0') and len(phone) == 10:
                        phone = '0' + phone
                    if not phone.startswith('09') or len(phone) != 11:
                        errors.append(f'ردیف {row_idx}: شماره {phone} نامعتبر')
                        continue

                    # ─── سن ───
                    age_raw = cell_value(row, 'age')
                    try:
                        age = int(age_raw) if age_raw else 1
                        if not 1 <= age <= 120:
                            age = 1
                    except (ValueError, TypeError):
                        age = 1

                    national_code = cell_value(row, 'national_code')
                    reshte = cell_value(row, 'reshte') or 'ثبت نشده'
                    school = cell_value(row, 'school') or 'ثبت نشده'
                    city = cell_value(row, 'city') or 'ثبت نشده'
                    moaref = cell_value(row, 'moaref') or None
                    created_str = cell_value(row, 'created_at')

                    # ─── ساخت/آپدیت دانشجو ───
                    student, created = Student.objects.get_or_create(
                        phone_number=phone,
                        defaults={
                            'name': name,
                            'age': age,
                            'national_code': national_code,
                            'reshte': reshte,
                            'school': school,
                            'city': city,
                            'moaref': moaref,
                        }
                    )

                    if created:
                        added_students += 1
                    else:
                        # اگه دانشجو وجود داشت، فیلدهای خالی رو پر کن (بدون override)
                        changed = []
                        for field, val in [
                            ('name', name), ('age', age),
                            ('national_code', national_code),
                            ('reshte', reshte), ('school', school),
                            ('city', city), ('moaref', moaref),
                        ]:
                            if val and not getattr(student, field):
                                setattr(student, field, val)
                                changed.append(field)
                        if changed:
                            student.save(update_fields=changed)
                            updated_students += 1

                    # ─── تنظیم created_at اگه توی اکسل بود ───
                    if created_str:
                        try:
                            dt = datetime.strptime(str(created_str), '%Y/%m/%d %H:%M')
                            if timezone.is_naive(dt):
                                dt = timezone.make_aware(dt)
                            Student.objects.filter(pk=student.pk).update(created_at=dt)
                            student.created_at = dt
                        except ValueError:
                            errors.append(f'ردیف {row_idx}: تاریخ نامعتبر — {created_str}')

                    # ─── منبع معرفی (اگه جدید بود) ───
                    referral_code = cell_value(row, 'referral_code')
                    if referral_code:
                        source = ReferralSource.objects.filter(code=str(referral_code).strip()).first()
                        if source and not student.referred_by:
                            student.referred_by = source
                            student.save(update_fields=['referred_by'])

                    # ─── پیدا کردن بوت‌کمپ ───
                    if is_legacy:
                        bootcamp = default_bootcamp
                    else:
                        slug = cell_value(row, 'bootcamp')
                        if not slug:
                            errors.append(f'ردیف {row_idx}: ستون دوره خالی')
                            continue
                        bootcamp = Bootcamp.objects.filter(slug=str(slug).strip()).first()
                        if not bootcamp:
                            errors.append(f'ردیف {row_idx}: بوت‌کمپ «{slug}» پیدا نشد')
                            continue

                    # ─── با مدرک؟ ───
                    if 'with_certificate' in col:
                        with_cert_raw = cell_value(row, 'with_certificate')
                        with_cert = str(with_cert_raw).lower() in ('true', '1', 'بله', 'بلی', 'yes')
                    else:
                        # قدیمی: اگه is_certified داشت، پس با مدرک بوده
                        cert_raw = cell_value(row, 'is_certified')
                        with_cert = str(cert_raw).lower() in ('true', '1', 'بله', 'بلی', 'yes')

                    # ─── is_certified ───
                    cert_raw = cell_value(row, 'is_certified')
                    is_cert = str(cert_raw).lower() in ('true', '1', 'بله', 'بلی', 'yes')

                    # ─── ساخت/آپدیت Enrollment ───
                    enrollment, e_created = Enrollment.objects.get_or_create(
                        student=student,
                        bootcamp=bootcamp,
                        defaults={
                            'with_certificate': with_cert or is_cert,
                            'is_active': True,
                            'is_certified': is_cert,
                            'registration_payment_submitted': True,
                            'registration_paid_at': student.created_at,
                            'certificate_issued_at': student.created_at if is_cert else None,
                        }
                    )

                    if e_created:
                        added_enrollments += 1
                    else:
                        # آپدیت اگه لازم بود
                        changed = []
                        if is_cert and not enrollment.is_certified:
                            enrollment.is_certified = True
                            enrollment.certificate_issued_at = student.created_at
                            changed.extend(['is_certified', 'certificate_issued_at'])
                        if with_cert and not enrollment.with_certificate:
                            enrollment.with_certificate = True
                            changed.append('with_certificate')
                        if not enrollment.is_active:
                            enrollment.is_active = True
                            changed.append('is_active')
                        if changed:
                            enrollment.save(update_fields=changed)

                except Exception as e:
                    errors.append(f'ردیف {row_idx}: {e}')

        # ─── گزارش ───
        summary = []
        if added_students:
            summary.append(f'👤 {added_students} دانشجوی جدید')
        if updated_students:
            summary.append(f'✏️ {updated_students} دانشجوی به‌روزشده')
        if added_enrollments:
            summary.append(f'📚 {added_enrollments} ثبت‌نام جدید')

        if summary:
            messages.success(request, '✅ ' + ' — '.join(summary))

        for err in errors[:8]:
            messages.warning(request, f'⚠️ {err}')
        if len(errors) > 8:
            messages.info(request, f'و {len(errors) - 8} خطای دیگر.')

        return redirect('core:students')

    except Exception as e:
        messages.error(request, f'❌ خطا در خواندن فایل: {e}')
        return redirect('core:import_excel')