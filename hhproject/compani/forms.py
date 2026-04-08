import re

from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import FileExtensionValidator

from home.forms import BaseUserCreationForm
from home.models import *


PHONE_ALLOWED_RE = re.compile(r"^[\d\s()+-]+$")
COMPANY_NAME_RE = re.compile(r"^[0-9A-Za-z\u0400-\u04FF\s\"'().,&-]+$")
INDUSTRY_RE = re.compile(r"^[0-9A-Za-z\u0400-\u04FF\s\"'().,&/-]+$")


def _normalize_ru_phone(value: str) -> str | None:
    raw = (value or "").strip()
    if not raw or not PHONE_ALLOWED_RE.fullmatch(raw):
        return None

    digits = re.sub(r"\D", "", raw)
    if len(digits) == 10:
        digits = f"7{digits}"
    elif len(digits) == 11 and digits[0] in ("7", "8"):
        digits = f"7{digits[1:]}"
    else:
        return None

    normalized = f"+{digits}"
    if re.fullmatch(r"\+7\d{10}", normalized):
        return normalized
    return None


class CompanyRegistrationApiForm(forms.Form):
    company_name = forms.CharField(
        max_length=100,
        min_length=2,
        required=True,
        label="Название компании",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Название вашей компании",
                "autocomplete": "organization",
            }
        ),
    )
    company_number = forms.CharField(
        max_length=10,
        min_length=10,
        required=True,
        label="ИНН",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "10 цифр ИНН",
                "autocomplete": "off",
                "inputmode": "numeric",
            }
        ),
    )
    industry = forms.CharField(
        max_length=100,
        min_length=2,
        required=True,
        label="Сфера деятельности",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Например, IT, строительство",
                "autocomplete": "off",
            }
        ),
    )
    description = forms.CharField(
        required=True,
        min_length=10,
        label="Описание",
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 4,
                "placeholder": "Кратко опишите компанию",
            }
        ),
    )
    email = forms.EmailField(
        required=True,
        label="Email",
        widget=forms.EmailInput(
            attrs={
                "class": "form-control",
                "placeholder": "example@company.com",
                "autocomplete": "email",
            }
        ),
    )
    phone = forms.CharField(
        max_length=80,
        required=True,
        label="Телефон",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "+7 (999) 999-99-99",
                "autocomplete": "tel",
            }
        ),
    )
    verification_document = forms.FileField(
        required=True,
        label="Подтверждающий документ (PDF)",
        validators=[FileExtensionValidator(["pdf"])],
        widget=forms.FileInput(
            attrs={
                "class": "form-control",
                "accept": ".pdf",
            }
        ),
    )
    password1 = forms.CharField(
        min_length=8,
        required=True,
        label="Пароль",
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "Минимум 8 символов",
                "autocomplete": "new-password",
            }
        ),
    )
    password2 = forms.CharField(
        min_length=8,
        required=True,
        label="Подтверждение пароля",
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "Повторите пароль",
                "autocomplete": "new-password",
            }
        ),
    )
    personal_data_agreement = forms.BooleanField(
        required=True,
        label="Я согласен на обработку персональных данных",
        error_messages={
            "required": "Необходимо согласие на обработку персональных данных.",
        },
    )

    def clean_company_name(self):
        value = (self.cleaned_data.get("company_name") or "").strip()
        if not COMPANY_NAME_RE.fullmatch(value):
            raise forms.ValidationError(
                "В названии компании допустимы буквы, цифры, пробелы и знаки: . , - & ( )"
            )
        if len(re.sub(r"[^0-9A-Za-z\u0400-\u04FF]", "", value)) < 2:
            raise forms.ValidationError("Название компании слишком короткое.")
        return value

    def clean_company_number(self):
        value = (self.cleaned_data.get("company_number") or "").strip()
        if not value.isdigit():
            raise forms.ValidationError("ИНН должен содержать только цифры.")
        if len(value) != 10:
            raise forms.ValidationError("ИНН должен содержать ровно 10 цифр.")
        return value

    def clean_industry(self):
        value = (self.cleaned_data.get("industry") or "").strip()
        if not INDUSTRY_RE.fullmatch(value):
            raise forms.ValidationError(
                "Поле сферы деятельности содержит недопустимые символы."
            )
        return value

    def clean_description(self):
        value = (self.cleaned_data.get("description") or "").strip()
        if len(value) < 10:
            raise forms.ValidationError("Описание должно быть не короче 10 символов.")
        return value

    def clean_phone(self):
        value = self.cleaned_data.get("phone") or ""
        normalized = _normalize_ru_phone(value)
        if not normalized:
            raise forms.ValidationError(
                "Телефон должен быть в формате +7XXXXXXXXXX и содержать только цифры."
            )
        return normalized

    def clean_verification_document(self):
        document = self.cleaned_data.get("verification_document")
        if not document:
            raise forms.ValidationError("Добавьте подтверждающий документ в формате PDF.")
        if document.size > 5 * 1024 * 1024:
            raise forms.ValidationError("Размер PDF не должен превышать 5 МБ.")
        return document

    def clean_password1(self):
        password = self.cleaned_data.get("password1") or ""
        if not re.search(r"[A-Za-z\u0400-\u04FF]", password):
            raise forms.ValidationError("Пароль должен содержать хотя бы одну букву.")
        if not re.search(r"\d", password):
            raise forms.ValidationError("Пароль должен содержать хотя бы одну цифру.")
        try:
            validate_password(password)
        except DjangoValidationError as exc:
            raise forms.ValidationError(exc.messages)
        return password

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            self.add_error("password2", "Пароли не совпадают.")
        return cleaned_data


class CompanySignUpForm(BaseUserCreationForm):
    company_name = forms.CharField(
        max_length=100, 
        required=True, 
        label="Название компании",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Название вашей компании',
            'autocomplete': 'organization'
        })
    )
    company_number = forms.CharField(
        max_length=10, 
        required=True, 
        label="ИНН",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '1234567890',
            'autocomplete': 'off'
        })
    )
    industry = forms.CharField(
        max_length=100, 
        required=True, 
        label="Сфера деятельности",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Например, IT, строительство',
            'autocomplete': 'off'
        })
    )
    description = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'placeholder': 'Опишите вашу компанию',
            'rows': 4
        }), 
        label="Описание компании"
    )
    theme = forms.CharField(
        max_length=100, 
        required=False, 
        label="Тема", 
        help_text="Опционально",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Тема оформления',
            'autocomplete': 'off'
        })
    )
    email = forms.EmailField(
        required=True, 
        label="Email",
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'example@company.com',
            'autocomplete': 'email'
        })
    )
    phone = forms.CharField(
        max_length=80, 
        required=True, 
        label="Телефон",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '+7 (999) 999-99-99',
            'autocomplete': 'tel'
        })
    )
    verification_document = forms.FileField(
        required=True,
        label="Подтверждающий документ",
        help_text="Загрузите документ, подтверждающий регистрацию компании (PDF, до 5MB)",
        widget=forms.FileInput(attrs={
            'class': 'form-control file-input',
            'accept': '.pdf',
        }),
        validators=[FileExtensionValidator(['pdf'])]
    )
    
    password1 = forms.CharField(
        label="Пароль",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Введите пароль',
            'autocomplete': 'new-password'
        })
    )
    password2 = forms.CharField(
        label="Подтверждение пароля",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Повторите пароль',
            'autocomplete': 'new-password'
        })
    )

    class Meta:
        model = User
        fields = ('email', 'phone', 'company_name', 'company_number', 'industry', 'description', 'theme', 'verification_document')
    def save(self, commit=True):
        user = super().save(commit=False)
        user.user_type = 'company'
        user.phone = self.cleaned_data['phone']
        if commit:
            try:
                user.save()
                Company.objects.update_or_create(
                    user=user,
                    defaults={
                        'name': self.cleaned_data['company_name'],
                        'number': self.cleaned_data['company_number'],
                        'industry': self.cleaned_data['industry'],
                        'description': self.cleaned_data['description'],
                        'theme': self.cleaned_data.get('theme', ''),
                        'verification_document': self.cleaned_data['verification_document']
                    }
                )
            except Exception as e:
                if user.pk:
                    user.delete()
                raise e
        return user

class CompanyProfileEditForm(forms.ModelForm):
    company_name = forms.CharField(
        max_length=100, 
        required=True, 
        label="Название компании",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Название вашей компании',
            'autocomplete': 'organization'
        })
    )
    company_number = forms.CharField(
        max_length=10, 
        required=True, 
        label="ИНН",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '1234567890',
            'autocomplete': 'off'
        })
    )
    industry = forms.CharField(
        max_length=100, 
        required=True, 
        label="Сфера деятельности",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Например, IT, строительство',
            'autocomplete': 'off'
        })
    )
    description = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'placeholder': 'Опишите вашу компанию',
            'rows': 4
        }), 
        label="Описание компании"
    )
    email = forms.EmailField(
        required=True, 
        label="Email",
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'example@company.com',
            'autocomplete': 'email'
        })
    )
    phone = forms.CharField(
        max_length=80, 
        required=True, 
        label="Телефон",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '+7 (999) 999-99-99',
            'autocomplete': 'tel'
        })
    )

    class Meta:
        model = User
        fields = ('email', 'phone')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.phone = self.cleaned_data['phone']
        if commit:
            try:
                user.save()
                Company.objects.update_or_create(
                    user=user,
                    defaults={
                        'name': self.cleaned_data['company_name'],
                        'number': self.cleaned_data['company_number'],
                        'industry': self.cleaned_data['industry'],
                        'description': self.cleaned_data['description']
                    }
                )
            except Exception as e:
                raise e
        return user

class PasswordResetRequestForm(forms.Form):
    email = forms.EmailField(
        required=True,
        label="Email",
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Введите ваш email',
            'autocomplete': 'email'
        })
    )

class PasswordResetConfirmForm(forms.Form):
    new_password1 = forms.CharField(
        label="Новый пароль",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Не менее 8 символов',
            'autocomplete': 'new-password'
        })
    )
    new_password2 = forms.CharField(
        label="Подтверждение пароля",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Повторите пароль',
            'autocomplete': 'new-password'
        })
    )

    def clean(self):
        cleaned_data = super().clean()
        new_password1 = cleaned_data.get("new_password1")
        new_password2 = cleaned_data.get("new_password2")
        if new_password1 and new_password2 and new_password1 != new_password2:
            raise forms.ValidationError("Пароли не совпадают")
        return cleaned_data
    
class ResponseStatusUpdateForm(forms.ModelForm):
    class Meta:
        model = Response
        fields = ['status']
        widgets = {
            'status': forms.Select(attrs={
                'class': 'response-status-select',
                'onchange': 'this.form.submit()'
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Можно добавить кастомные labels или queryset если нужно

class HRAgentCreateForm(BaseUserCreationForm):
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
    email = forms.EmailField(
        required=True,
        label="Email",
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'example@email.com',
            'autocomplete': 'email'
        })
    )
    phone = forms.CharField(
        max_length=80,
        required=True,
        label="Телефон",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '+7 (999) 999-99-99',
            'autocomplete': 'tel'
        })
    )

    class Meta:
        model = User
        fields = ('email', 'phone', 'password1', 'password2', 'first_name', 'last_name')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
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

    def save(self, commit=True, company=None):
        user = super().save(commit=False)
        user.username = user.email
        user.user_type = 'hragent'
        if commit:
            user.save()
            Employee.objects.create(
                user=user,
                first_name=self.cleaned_data['first_name'],
                last_name=self.cleaned_data['last_name'],
                company=company,
                access_level='hr'
            )
        return user
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator

class HRAgentImportForm(forms.Form):
    csv_file = forms.FileField(
        label='CSV файл',
        help_text='Файл должен содержать колонки: first_name, last_name, email, phone. Рекомендуемая кодировка: UTF-8',
        validators=[FileExtensionValidator(allowed_extensions=['csv'])],
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.csv',
            'required': True
        })
    )

    def clean_csv_file(self):
        csv_file = self.cleaned_data['csv_file']
        
        if not csv_file.name.endswith('.csv'):
            raise ValidationError('Файл должен быть в формате CSV (.csv)')
        
        # Проверяем размер файла (максимум 5MB)
        if csv_file.size > 5 * 1024 * 1024:
            raise ValidationError('Файл слишком большой. Максимальный размер: 5MB')
        
        if csv_file.size == 0:
            raise ValidationError('Файл пустой')
        
        # Пробуем прочитать файл для проверки кодировки
        try:
            sample = csv_file.read(1024)  # Читаем первые 1024 байта
            csv_file.seek(0)  # Возвращаем позицию чтения
            
            # Пробуем разные кодировки
            encodings = ['utf-8-sig', 'cp1251', 'windows-1251', 'iso-8859-1', 'utf-8']
            for encoding in encodings:
                try:
                    sample.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                raise ValidationError('Не удалось определить кодировку файла. Пожалуйста, сохраните файл в UTF-8.')
                
        except Exception as e:
            raise ValidationError(f'Ошибка при проверке файла: {str(e)}')
        
        return csv_file

class HRAgentEditForm(forms.ModelForm):
    email = forms.EmailField(
        required=True,
        label="Email",
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'example@email.com',
            'autocomplete': 'email'
        })
    )
    phone = forms.CharField(
        max_length=80,
        required=True,
        label="Телефон",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '+7 (999) 999-99-99',
            'autocomplete': 'tel'
        })
    )

    class Meta:
        model = Employee
        fields = ('first_name', 'last_name')
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ваше имя',
                'autocomplete': 'given-name'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ваша фамилия',
                'autocomplete': 'family-name'
            }),
        }


class VacancyForm(forms.ModelForm):
    work_conditions = forms.ModelChoiceField(
        queryset=WorkConditions.objects.all(),
        label="Тип занятости",
        widget=forms.Select(attrs={
            'class': 'form-control',
            'placeholder': 'Выберите тип занятости',
        })
    )
    position = forms.CharField(
        max_length=100,
        required=True,
        label="Должность",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Введите должность',
            'autocomplete': 'off'
        })
    )
    description = forms.CharField(
        required=True,
        label="Описание",
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Введите описание вакансии'
        })
    )
    requirements = forms.CharField(
        required=True,
        label="Требования",
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Введите требования'
        })
    )
    salary_min = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=True,
        label="Минимальная зарплата, ₽",
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '0.00',
            'step': '0.01'
        })
    )
    salary_max = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=True,
        label="Максимальная зарплата, ₽",
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '0.00',
            'step': '0.01'
        })
    )
    experience = forms.ChoiceField(
        choices=[('', 'Не указан')] + list(Vacancy._meta.get_field('experience').choices),
        required=False,
        label="Опыт работы",
        widget=forms.Select(attrs={
            'class': 'form-control',
            'placeholder': 'Выберите опыт'
        })
    )
    city = forms.CharField(
        max_length=100,
        required=True,
        label="Город",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Введите город',
            'autocomplete': 'off'
        })
    )
    category = forms.ChoiceField(
        choices=[('', 'Не указана')] + list(Vacancy._meta.get_field('category').choices),
        required=False,
        label="Категория",
        widget=forms.Select(attrs={
            'class': 'form-control',
            'placeholder': 'Выберите категорию'
        })
    )
    work_conditions_details = forms.CharField(
        required=False,
        label="Детали условий",
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Введите детали условий (по одной строке)'
        })
    )
    status = forms.ModelChoiceField(
        queryset=StatusVacancies.objects.all(),
        label="Статус",
        widget=forms.Select(attrs={
            'class': 'form-control',
            'placeholder': 'Выберите статус'
        })
    )

    class Meta:
        model = Vacancy
        fields = ['work_conditions', 'position', 'description', 'requirements', 'salary_min', 'salary_max', 'experience', 'city', 'category', 'work_conditions_details', 'status']

class ResponseStatusUpdateForm(forms.ModelForm):
    status = forms.ModelChoiceField(
        queryset=StatusResponse.objects.all(),
        label="Статус отклика",
        widget=forms.Select(attrs={
            'class': 'form-control',
            'placeholder': 'Выберите статус'
        })
    )

    class Meta:
        model = Response
        fields = ['status']
        
class EmployeeProfileForm(forms.ModelForm):
    first_name = forms.CharField(
        max_length=150,
        label='Имя',
        widget=forms.TextInput(attrs={'class': 'form-input'}),
        required=True
    )
    last_name = forms.CharField(
        max_length=150,
        label='Фамилия',
        widget=forms.TextInput(attrs={'class': 'form-input'}),
        required=True
    )
    email = forms.EmailField(
        label='Email',
        widget=forms.EmailInput(attrs={'class': 'form-input'}),
        required=True
    )
    phone = forms.CharField(
        max_length=80,
        label='Телефон',
        widget=forms.TextInput(attrs={'class': 'form-input'}),
        required=False
    )

    class Meta:
        model = Employee
        fields = ['theme']
        widgets = {
            'theme': forms.TextInput(attrs={'class': 'form-input'}),
        }
        labels = {
            'theme': 'Специализация',
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if self.user:
            # Приоритет: данные из Employee, если пусто — из User
            self.fields['first_name'].initial = self.instance.first_name or self.user.first_name
            self.fields['last_name'].initial = self.instance.last_name or self.user.last_name
            self.fields['email'].initial = self.user.email
            self.fields['phone'].initial = getattr(self.user, 'phone', '') or ''

    def save(self, commit=True):
        employee = super().save(commit=False)

        # Синхронизация в обе стороны
        first_name = self.cleaned_data['first_name']
        last_name = self.cleaned_data['last_name']

        employee.first_name = first_name
        employee.last_name = last_name

        if self.user:
            self.user.first_name = first_name
            self.user.last_name = last_name
            self.user.email = self.cleaned_data['email']
            self.user.phone = self.cleaned_data['phone'] or ''
            if commit:
                self.user.save()

        if commit:
            employee.save()

        return employee
