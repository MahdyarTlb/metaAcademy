from django import forms
from .models import Student

class StudentForm(forms.ModelForm):
    class Meta:
        model = Student
        fields = ['name', 'age', 'phone_number', 'reshte', 'school', 'city', 'moaref']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'نام کامل فارسی برای صدور مدرک'}),
            'age': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 120}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '09123456789'}),
            'reshte': forms.TextInput(attrs={'class': 'form-control'}),
            'school': forms.TextInput(attrs={'class': 'form-control'}),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'moaref': forms.TextInput(attrs={'class': 'form-control'}),
        }

class ExcelUploadForm(forms.Form):
    excel_file = forms.FileField(
        label='فایل اکسل',
        help_text='فایل با فرمت .xlsx و شامل ستون‌های: نام, سن, تلفن, رشته, مدرسه, شهر, معرف',
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.xlsx,.xls'
        })
    )
    
class CheckForm(forms.Form):
    phone = forms.CharField(
        label='شماره موبایل',
        max_length=20,
        widget=forms.TextInput(attrs={
            'placeholder': '(فقط با اعداد انگلیسی) ۰۹۱۲۳۴۵۶۷۸۹',
            'dir': 'ltr',
            'class': 'check-input',
        })
    )