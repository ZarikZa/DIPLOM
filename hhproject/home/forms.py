from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import User, Company, Applicant, Employee, Role, Complaint
from django.utils import timezone
from datetime import timedelta
from django.core.exceptions import ValidationError

class CustomAuthenticationForm(AuthenticationForm):
    username = forms.EmailField(label='Email')
    
    class Meta:
        model = User
        fields = ['username', 'password']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.fields['username'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Введите email',
            'autocomplete': 'email'
        })
        
        self.fields['password'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Введите пароль', 
            'autocomplete': 'current-password'
        })
    
class BaseUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True, label="Email")
    phone = forms.CharField(max_length=80, required=True, label="Телефон")
    
    class Meta:
        model = User
        fields = ('email', 'phone', 'password1', 'password2')
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = user.email  
        if commit:
            user.save()
        return user

class ApplicantSignUpForm(BaseUserCreationForm):
    first_name = forms.CharField(
        max_length=80, 
        required=True, 
        label="Имя",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ваше имя',
            'autocomplete': 'given-name'
        })
    )
    
    last_name = forms.CharField(
        max_length=80, 
        required=True, 
        label="Фамилия",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ваша фамилия', 
            'autocomplete': 'family-name'
        })
    )
    
    birth_date = forms.DateField(
        required=True, 
        label="Дата рождения",
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control',
            'placeholder': 'дд.мм.гггг'
        })
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.fields['email'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'example@email.com',
            'autocomplete': 'email'
        })
        
        self.fields['phone'].widget.attrs.update({
            'class': 'form-control', 
            'placeholder': '+7 (999) 999-99-99',
            'autocomplete': 'tel'
        })
        
        self.fields['password1'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Не менее 8 символов',
            'autocomplete': 'new-password'
        })
        
        self.fields['password2'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Повторите пароль',
            'autocomplete': 'new-password'
        })
    
    def clean_birth_date(self):
        birth_date = self.cleaned_data.get('birth_date')
        
        if birth_date:
            today = timezone.now().date()
            
            # Проверка что дата не в будущем
            if birth_date > today:
                raise ValidationError(
                    "Дата рождения не может быть в будущем."
                )
            
            # Проверка возраста (14 лет)
            min_age_date = today - timedelta(days=365 * 14 + 4)  # 14 лет + 4 дня для високосных годов
            
            if birth_date > min_age_date:
                raise ValidationError(
                    "Для регистрации вам должно быть не менее 14 лет."
                )
        
        return birth_date
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.user_type = 'applicant'
        if commit:
            user.save()
            Applicant.objects.create(
                user=user,
                first_name=self.cleaned_data['first_name'],
                last_name=self.cleaned_data['last_name'],
                birth_date=self.cleaned_data['birth_date']
            )
        return user


class ApplicantEditForm(forms.ModelForm):
    class Meta:
        model = Applicant
        fields = ['first_name', 'last_name', 'birth_date', 'resume']
        widgets = {
            'birth_date': forms.DateInput(attrs={'type': 'date'}),
            'resume': forms.Textarea(attrs={'rows': 6}),
        }

class UserEditForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['email', 'phone']

class PasswordResetRequestForm(forms.Form):
    email = forms.EmailField(
        max_length=254, 
        required=True,
        label="Email",
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'example@email.com',
            'autocomplete': 'email'
        })
    )

class CodeVerificationForm(forms.Form):
    code = forms.CharField(
        max_length=6,
        min_length=6,
        required=True,
        label="Код подтверждения", 
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Введите 6-значный код',
            'autocomplete': 'one-time-code'
        })
    )

class SetNewPasswordForm(forms.Form):
    new_password1 = forms.CharField(
        required=True,
        label="Новый пароль",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Не менее 8 символов',
            'autocomplete': 'new-password'
        }),
        min_length=8
    )
    
    new_password2 = forms.CharField(
        required=True,
        label="Подтвердите пароль",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Повторите пароль',
            'autocomplete': 'new-password'
        })
    )

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('new_password1')
        password2 = cleaned_data.get('new_password2')

        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Пароли не совпадают")
        
        return cleaned_data
    

class ComplaintForm(forms.ModelForm):
    class Meta:
        model = Complaint
        fields = ['complaint_type', 'description']
        widgets = {
            'complaint_type': forms.Select(attrs={
                'class': 'form-select',
                'required': True,
                'id': 'id_complaint_type'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-textarea',
                'rows': 4,
                'placeholder': 'Опишите подробнее причину жалобы...',
                'id': 'id_description'
            })
        }
        labels = {
            'complaint_type': 'Тип жалобы',
            'description': 'Дополнительная информация'
        }
