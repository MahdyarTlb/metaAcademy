from django import forms
from .models import Student
from django.contrib.auth.hashers import make_password
from django.core.exceptions import ValidationError

class StudentForm(forms.ModelForm):
    password1 = forms.CharField(
        label='رمز عبور',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'حداقل ۶ کاراکتر',
        }),
    )
    password2 = forms.CharField(
        label='تکرار رمز عبور',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'رمز عبور را دوباره وارد کنید',
        }),
    )

    class Meta:
        model = Student
        fields = ['name', 'age', 'phone_number', 'email', 'reshte', 'school', 'city', 'moaref']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'نام کامل فارسی برای صدور مدرک'}),
            'age': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 120}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': ' با اعداد انگلیسی 09123456789'}),
            'email': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'email@gmail.com'}),
            'reshte': forms.TextInput(attrs={'class': 'form-control'}),
            'school': forms.TextInput(attrs={'class': 'form-control'}),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'moaref': forms.TextInput(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['phone_number'].required = True
        self.fields['phone_number'].error_messages = {
            'required': 'شماره تلفن الزامی است.'
        }

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get('password1')
        p2 = cleaned_data.get('password2')

        if p1 and len(p1) < 6:
            self.add_error('password1', 'رمز عبور باید حداقل ۶ کاراکتر باشد.')
        if p1 and p2 and p1 != p2:
            self.add_error('password2', 'رمز عبور و تکرار آن یکسان نیستند.')
        return cleaned_data

    def save(self, commit=True):
        student = super().save(commit=False)
        student.password = make_password(self.cleaned_data['password1'])
        if commit:
            student.save()
        return student


class CheckForm(forms.Form):
    identifier = forms.CharField(
        label='شماره موبایل یا ایمیل',
        max_length=254,
        widget=forms.TextInput(attrs={
            'placeholder': 'موبایل یا ایمیل',
            'dir': 'ltr',
            'class': 'check-input',
        })
    )


class SetPasswordForm(forms.Form):
    password1 = forms.CharField(
        label='رمز عبور جدید',
        widget=forms.PasswordInput(attrs={
            'class': 'check-input',
            'placeholder': 'حداقل ۶ کاراکتر',
        }),
    )
    password2 = forms.CharField(
        label='تکرار رمز عبور',
        widget=forms.PasswordInput(attrs={
            'class': 'check-input',
            'placeholder': 'رمز عبور را دوباره وارد کنید',
        }),
    )

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get('password1')
        p2 = cleaned_data.get('password2')

        if p1 and len(p1) < 6:
            raise forms.ValidationError('رمز عبور باید حداقل ۶ کاراکتر باشد.')
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError('رمز عبور و تکرار آن یکسان نیستند.')
        return cleaned_data


class LoginPasswordForm(forms.Form):
    password = forms.CharField(
        label='رمز عبور',
        widget=forms.PasswordInput(attrs={
            'class': 'check-input',
            'placeholder': 'رمز عبور خود را وارد کنید',
        }),
    )
    
class ExcelUploadForm(forms.Form):
    excel_file = forms.FileField(
        label='فایل اکسل',
        help_text='فایل با فرمت .xlsx و شامل ستون‌های: نام, سن, تلفن, رشته, مدرسه, شهر, معرف',
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.xlsx,.xls'
        })
    )

class CertificateForm(forms.Form):
    name = forms.CharField(
        max_length=50,
        label='نام و نام خانوادگی',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'نام و نام خانوادگی خود را وارد کنید'
        })
    )
    
    national_code = forms.CharField(
        max_length=10,
        min_length=10,
        label='کد ملی',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'کد ملی خود را وارد کنید',
            'pattern': '[0-9]{10}',
            'title': 'کد ملی باید ۱۰ رقم باشد'
        })
    )
    
    def clean_national_code(self):
        national_code = self.cleaned_data.get('national_code')
        # حذف فاصله‌ها
        national_code = national_code.replace(' ', '')
        # بررسی اینکه فقط عدد باشد
        if not national_code.isdigit():
            raise ValidationError('کد ملی باید فقط شامل اعداد باشد')
        # بررسی طول
        if len(national_code) != 10:
            raise ValidationError('کد ملی باید دقیقاً ۱۰ رقم باشد')
        
        return national_code