from django import forms
from .models import Student
from django.contrib.auth.hashers import make_password

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
        max_length=20,
        widget=forms.TextInput(attrs={
            'placeholder': 'موبایل یا ایمیل',
            'dir': 'ltr',
            'class': 'check-input',
        })
    )


class SetPasswordForm(forms.Form):
    """برای کاربرانی که قبلاً بدون رمز ثبت‌نام کرده‌اند و اولین‌بار وارد پنل می‌شوند."""

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
    """برای کاربرانی که رمز عبور دارند و می‌خواهند وارد پنل شوند."""

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