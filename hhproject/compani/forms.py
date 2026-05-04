import re

from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import FileExtensionValidator


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


__all__ = ["CompanyRegistrationApiForm"]
