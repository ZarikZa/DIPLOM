import re

from datetime import date
from decimal import Decimal

from django.contrib.auth.password_validation import validate_password
from django.core.validators import FileExtensionValidator
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from .email_service import send_company_status_email
from .models import *
from .text_validation import ProfanityValidator


PHONE_ALLOWED_RE = re.compile(r"^[\d\s()+-]+$")
COMPANY_NAME_RE = re.compile(r"^[0-9A-Za-z\u0400-\u04FF\s\"'().,&-]+$")
INDUSTRY_RE = re.compile(r"^[0-9A-Za-z\u0400-\u04FF\s\"'().,&/-]+$")
PERSON_NAME_RE = re.compile(r"^[A-Za-z\u0400-\u04FF\s'-]+$")
CITY_RE = re.compile(r"^[0-9A-Za-z\u0400-\u04FF\s'().,-]+$")
POSITION_RE = re.compile(r"^[0-9A-Za-z\u0400-\u04FF\s'().,+/#-]+$")
CATEGORY_NAME_RE = re.compile(r"^[0-9A-Za-z\u0400-\u04FF\s'().,+/#&-]+$")
RESUME_FILE_ALLOWED_EXTENSIONS = ['pdf', 'doc', 'docx', 'rtf', 'txt']
RESUME_FILE_MAX_SIZE = 10 * 1024 * 1024
MAX_VIDEOS_PER_VACANCY = 3


def normalize_ru_phone(value: str) -> str | None:
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


def _normalize_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def _validate_no_profanity(value: str, field_label: str) -> str:
    try:
        return ProfanityValidator.ensure_clean(value, field_label)
    except ValueError as exc:
        raise serializers.ValidationError(str(exc))


def _validate_person_name(value: str, field_label: str) -> str:
    value = _normalize_text(value)
    if len(value) < 2:
        raise serializers.ValidationError(f'{field_label} должно содержать минимум 2 символа.')
    if not PERSON_NAME_RE.fullmatch(value):
        raise serializers.ValidationError(
            f'{field_label} может содержать только буквы, пробел, дефис и апостроф.'
        )
    return _validate_no_profanity(value, field_label)


def _validate_birth_date(value: date) -> date:
    today = date.today()
    if value > today:
        raise serializers.ValidationError('Дата рождения не может быть в будущем.')
    if value.year < 1900:
        raise serializers.ValidationError('Год рождения указан некорректно.')
    return value


def _validate_salary(value: Decimal, field_label: str) -> Decimal:
    if value < Decimal('0'):
        raise serializers.ValidationError(f'{field_label} не может быть меньше 0.')
    return value


def _validate_resume_file(file_obj):
    if not file_obj:
        return file_obj

    file_size = getattr(file_obj, 'size', None)
    if file_size is not None and file_size > RESUME_FILE_MAX_SIZE:
        raise serializers.ValidationError('Файл резюме не должен превышать 10 МБ.')

    file_name = str(getattr(file_obj, 'name', '') or '')
    extension = file_name.rsplit('.', 1)[-1].lower() if '.' in file_name else ''
    if extension not in RESUME_FILE_ALLOWED_EXTENSIONS:
        allowed = ', '.join(RESUME_FILE_ALLOWED_EXTENSIONS)
        raise serializers.ValidationError(f'Допустимые форматы файла резюме: {allowed}.')

    return file_obj


def _validate_vacancy_category_name(value: str) -> str:
    value = _normalize_text(value)
    if len(value) < 2:
        raise serializers.ValidationError('Название категории должно быть не короче 2 символов.')
    if len(value) > 50:
        raise serializers.ValidationError('Название категории не должно быть длиннее 50 символов.')
    if not CATEGORY_NAME_RE.fullmatch(value):
        raise serializers.ValidationError(
            'Категория содержит недопустимые символы. Разрешены буквы, цифры, пробелы и знаки . , - ( ) / # + &'
        )

    value = _validate_no_profanity(value, 'Категория')
    normalized = normalize_vacancy_category_name(value)

    default_categories = {
        normalize_vacancy_category_name(item)
        for item in DEFAULT_VACANCY_CATEGORIES
    }
    if normalized in default_categories:
        raise serializers.ValidationError('Такая категория уже есть в списке доступных.')

    existing = VacancyCategorySuggestion.objects.filter(normalized_name=normalized).first()
    if existing:
        if existing.status == VacancyCategorySuggestion.STATUS_PENDING:
            raise serializers.ValidationError(
                'Такая категория уже отправлена на проверку администратору.'
            )
        if existing.status == VacancyCategorySuggestion.STATUS_APPROVED:
            raise serializers.ValidationError(
                'Такая категория уже одобрена и доступна для выбора.'
            )
        raise serializers.ValidationError(
            'Такая категория уже существует и ранее была отклонена.'
        )
    return value


def _validate_skill_name(value: str) -> str:
    value = _normalize_text(value)
    if len(value) < 2:
        raise serializers.ValidationError('Название навыка должно быть не короче 2 символов.')
    if len(value) > 80:
        raise serializers.ValidationError('Название навыка не должно быть длиннее 80 символов.')
    if not CATEGORY_NAME_RE.fullmatch(value):
        raise serializers.ValidationError(
            'Навык содержит недопустимые символы. Разрешены буквы, цифры, пробелы и знаки . , - ( ) / # + &'
        )
    return _validate_no_profanity(value, 'Навык')


def _validate_vacancy_video_capacity(vacancy, exclude_video_id=None):
    qs = VacancyVideo.objects.filter(vacancy=vacancy)
    if exclude_video_id:
        qs = qs.exclude(id=exclude_video_id)

    if qs.count() >= MAX_VIDEOS_PER_VACANCY:
        raise serializers.ValidationError(
            f'К вакансии можно прикрепить не более {MAX_VIDEOS_PER_VACANCY} видео.'
        )
    return vacancy

class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True)
    
    class Meta:
        model = User
        fields = ('email', 'username', 'phone', 'password', 'password2', 'user_type')
    
    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password": "Пароли не совпадают"})
        return attrs
    
    def create(self, validated_data):
        validated_data.pop('password2')
        user = User.objects.create_user(**validated_data)
        return user

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'email', 'username', 'phone', 'user_type', 'first_name', 'last_name')
        read_only_fields = ('id', 'user_type')

class CompanySerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = Company
        fields = '__all__'
        read_only_fields = ('created_at', 'status')

    def validate_name(self, value):
        value = _normalize_text(value)
        if len(value) < 2:
            raise serializers.ValidationError('Название компании слишком короткое.')
        if not COMPANY_NAME_RE.fullmatch(value):
            raise serializers.ValidationError(
                'В названии компании допустимы буквы, цифры, пробелы и знаки: . , - & ( )'
            )
        return _validate_no_profanity(value, 'Название компании')

    def validate_number(self, value):
        value = _normalize_text(value)
        if not value.isdigit():
            raise serializers.ValidationError('ИНН должен содержать только цифры.')
        if len(value) != 10:
            raise serializers.ValidationError('ИНН должен содержать ровно 10 цифр.')
        return value

    def validate_industry(self, value):
        value = _normalize_text(value)
        if len(value) < 2:
            raise serializers.ValidationError('Сфера деятельности слишком короткая.')
        if not INDUSTRY_RE.fullmatch(value):
            raise serializers.ValidationError('Поле сферы деятельности содержит недопустимые символы.')
        return _validate_no_profanity(value, 'Сфера деятельности')

    def validate_description(self, value):
        value = _normalize_text(value)
        if len(value) < 10:
            raise serializers.ValidationError('Описание должно быть не короче 10 символов.')
        return _validate_no_profanity(value, 'Описание компании')

class CompanyStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ('id', 'status', 'admin_notes')
    
    def update(self, instance, validated_data):
        old_status = instance.status
        new_status = validated_data.get('status', instance.status)
        new_admin_notes = validated_data.get('admin_notes', instance.admin_notes)

        updated_fields = []
        if instance.status != new_status:
            instance.status = new_status
            updated_fields.append('status')
        if instance.admin_notes != new_admin_notes:
            instance.admin_notes = new_admin_notes
            updated_fields.append('admin_notes')

        if not updated_fields:
            return instance

        instance.save(update_fields=updated_fields)

        status_changed = old_status != instance.status
        email_sent = None
        if status_changed:
            email_sent = send_company_status_email(
                recipient_email=getattr(getattr(instance, 'user', None), 'email', ''),
                company_name=instance.name,
                new_status=instance.status,
                old_status=old_status,
                admin_notes=instance.admin_notes or '',
            )

        if status_changed:
            if instance.status == Company.STATUS_APPROVED:
                code = 'company_approved'
                name = 'Одобрение компании'
            elif instance.status == Company.STATUS_REJECTED:
                code = 'company_rejected'
                name = 'Отклонение компании'
            else:
                code = 'company_status_updated'
                name = 'Смена статуса компании'
            details = f"Статус изменен на {instance.get_status_display()}"
            if email_sent is not None:
                details += ' (email отправлен)' if email_sent else ' (ошибка отправки email)'
        else:
            code = 'company_moderation_updated'
            name = 'Обновление модерации компании'
            details = "Обновлены данные модерации"

        action_type, _ = ActionType.objects.get_or_create(
            code=code,
            defaults={"name": name, "description": ""},
        )

        request = self.context.get('request')
        if request and getattr(request, 'user', None):
            AdminLog.objects.create(
                admin=request.user,
                action=action_type,
                target_company=instance,
                details=details
            )
        return instance

class ApplicantSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    full_name = serializers.CharField(source='__str__', read_only=True)
    
    class Meta:
        model = Applicant
        fields = '__all__'


class SkillSerializer(serializers.ModelSerializer):
    def validate_name(self, value):
        value = _validate_skill_name(value)

        qs = Skill.objects.filter(name__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError('Такой навык уже существует.')

        return value

    class Meta:
        model = Skill
        fields = ('id', 'name')


class ApplicantSkillSuggestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApplicantSkillSuggestion
        fields = ('id', 'name', 'status', 'admin_notes', 'created_at', 'reviewed_at')
        read_only_fields = fields


class ApplicantSkillSuggestionCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=80)

    def validate_name(self, value):
        value = _validate_skill_name(value)
        normalized = normalize_vacancy_category_name(value)

        if Skill.objects.filter(name__iexact=value).exists():
            raise serializers.ValidationError('Такой навык уже существует в списке доступных.')

        applicant = self.context.get('applicant')
        if applicant is None:
            return value

        existing = (
            ApplicantSkillSuggestion.objects
            .filter(applicant=applicant, normalized_name=normalized)
            .order_by('-created_at')
            .first()
        )
        if existing and existing.status == ApplicantSkillSuggestion.STATUS_PENDING:
            raise serializers.ValidationError('Такой навык уже отправлен на проверку администратору.')
        if existing and existing.status == ApplicantSkillSuggestion.STATUS_APPROVED:
            raise serializers.ValidationError('Этот навык уже подтвержден администратором.')

        return value


class AdminApplicantSkillSuggestionSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    applicant_full_name = serializers.SerializerMethodField()
    applicant_email = serializers.CharField(source='applicant.user.email', read_only=True)
    requested_by_email = serializers.CharField(source='requested_by.email', read_only=True)
    reviewed_by_email = serializers.CharField(source='reviewed_by.email', read_only=True)

    class Meta:
        model = ApplicantSkillSuggestion
        fields = (
            'id',
            'name',
            'status',
            'status_display',
            'admin_notes',
            'applicant',
            'applicant_full_name',
            'applicant_email',
            'requested_by',
            'requested_by_email',
            'reviewed_by',
            'reviewed_by_email',
            'reviewed_at',
            'created_at',
        )
        read_only_fields = (
            'id',
            'name',
            'applicant',
            'applicant_full_name',
            'applicant_email',
            'requested_by',
            'requested_by_email',
            'reviewed_by',
            'reviewed_by_email',
            'reviewed_at',
            'created_at',
        )

    def get_applicant_full_name(self, obj):
        full_name = f"{obj.applicant.first_name} {obj.applicant.last_name}".strip()
        return full_name or obj.applicant.user.email


class AdminApplicantSkillSuggestionUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApplicantSkillSuggestion
        fields = ('status', 'admin_notes')

    def validate_admin_notes(self, value):
        value = _normalize_text(value)
        if not value:
            return ''
        return _validate_no_profanity(value, 'Комментарий администратора')


class ApplicantSkillSerializer(serializers.ModelSerializer):
    skill_name = serializers.CharField(source='skill.name', read_only=True)

    class Meta:
        model = ApplicantSkill
        fields = ('id', 'skill', 'skill_name', 'level')

    def validate_level(self, v):
        if v < 1 or v > 5:
            raise serializers.ValidationError('level должен быть от 1 до 5')
        return v


class ApplicantSkillUpsertSerializer(serializers.Serializer):
    """Приём пачки оценок навыков (upsert)."""

    skill_id = serializers.IntegerField()
    level = serializers.IntegerField(min_value=1, max_value=5)

class EmployeeSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    company_name = serializers.CharField(source='company.name', read_only=True)
    
    class Meta:
        model = Employee
        fields = '__all__'

class WorkConditionsSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkConditions
        fields = '__all__'

class StatusVacanciesSerializer(serializers.ModelSerializer):
    class Meta:
        model = StatusVacancies
        fields = '__all__'

class StatusResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = StatusResponse
        fields = '__all__'


class VacancyCategoryOptionSerializer(serializers.Serializer):
    name = serializers.CharField()


class CompanyVacancyCategorySuggestionCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=50)

    def validate_name(self, value):
        return _validate_vacancy_category_name(value)


class CompanyVacancyCategorySuggestionSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = VacancyCategorySuggestion
        fields = (
            'id',
            'name',
            'status',
            'status_display',
            'admin_notes',
            'created_at',
            'reviewed_at',
        )
        read_only_fields = fields


class AdminVacancyCategorySuggestionSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    company_name = serializers.CharField(source='company.name', read_only=True)
    requested_by_email = serializers.CharField(source='requested_by.email', read_only=True)
    reviewed_by_email = serializers.CharField(source='reviewed_by.email', read_only=True)

    class Meta:
        model = VacancyCategorySuggestion
        fields = (
            'id',
            'name',
            'status',
            'status_display',
            'admin_notes',
            'company',
            'company_name',
            'requested_by',
            'requested_by_email',
            'reviewed_by',
            'reviewed_by_email',
            'reviewed_at',
            'created_at',
        )
        read_only_fields = (
            'id',
            'name',
            'company',
            'company_name',
            'requested_by',
            'requested_by_email',
            'reviewed_by',
            'reviewed_by_email',
            'reviewed_at',
            'created_at',
        )


class AdminVacancyCategorySuggestionUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = VacancyCategorySuggestion
        fields = ('status', 'admin_notes')

    def validate_admin_notes(self, value):
        value = _normalize_text(value)
        if not value:
            return ''
        return _validate_no_profanity(value, 'Комментарий администратора')


class AdminVacancyCategorySuggestionCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=50)
    admin_notes = serializers.CharField(required=False, allow_blank=True)

    def validate_name(self, value):
        return _validate_vacancy_category_name(value)

    def validate_admin_notes(self, value):
        value = _normalize_text(value)
        if not value:
            return ''
        return _validate_no_profanity(value, 'Комментарий администратора')


class VacancyListSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source='company.name', read_only=True)
    work_conditions_name = serializers.CharField(source='work_conditions.work_conditions_name', read_only=True)
    status_name = serializers.CharField(source='status.status_vacancies_name', read_only=True)

    has_video = serializers.SerializerMethodField()
    video_id = serializers.SerializerMethodField()

    has_applied = serializers.SerializerMethodField()  # ✅

    class Meta:
        model = Vacancy
        fields = (
            'id', 'position', 'company_name',
            'salary_min', 'salary_max',
            'city', 'category', 'experience',
            'work_conditions_name', 'status_name',
            'views', 'created_date',
            'is_archived',
            'has_video', 'video_id',
            'has_applied',  # ✅
        )

    def get_has_video(self, obj):
        return obj.videos.exists()

    def get_video_id(self, obj):
        v = obj.videos.order_by('-created_at').first()
        return v.id if v else None

    def get_has_applied(self, obj):
        request = self.context.get("request")
        if not request or not request.user or not request.user.is_authenticated:
            return False

        # ---- ВАРИАНТ 1: если Response.applicants = FK на Applicant ----
        return Response.objects.filter(vacancy=obj, applicants__user=request.user).exists()

        # ---- ВАРИАНТ 2: если Response.applicants = FK на User ----
        # return Response.objects.filter(vacancy=obj, applicants=request.user).exists()



class VacancyDetailSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source='company.name', read_only=True)
    work_conditions_name = serializers.CharField(source='work_conditions.work_conditions_name', read_only=True)
    status_name = serializers.CharField(source='status.status_vacancies_name', read_only=True)
    category = serializers.CharField()
    has_applied = serializers.SerializerMethodField()  # Убедитесь, что это поле есть!
    is_favorite = serializers.SerializerMethodField()
    
    class Meta:
        model = Vacancy
        fields = '__all__'
    
    def get_has_applied(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            try:
                applicant = request.user.applicant
                return Response.objects.filter(applicants=applicant, vacancy=obj).exists()
            except Applicant.DoesNotExist:
                return False
        return False
    
    def get_is_favorite(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            try:
                applicant = request.user.applicant
                return Favorites.objects.filter(applicant=applicant, vacancy=obj).exists()
            except Applicant.DoesNotExist:
                return False
        return False

    def validate_position(self, value):
        value = _normalize_text(value)
        if len(value) < 2:
            raise serializers.ValidationError('Название должности слишком короткое.')
        if not POSITION_RE.fullmatch(value):
            raise serializers.ValidationError('Поле должности содержит недопустимые символы.')
        return _validate_no_profanity(value, 'Название должности')

    def validate_city(self, value):
        value = _normalize_text(value)
        if len(value) < 2:
            raise serializers.ValidationError('Название города слишком короткое.')
        if not CITY_RE.fullmatch(value):
            raise serializers.ValidationError('Поле города содержит недопустимые символы.')
        return _validate_no_profanity(value, 'Город')

    def validate_description(self, value):
        value = _normalize_text(value)
        if len(value) < 10:
            raise serializers.ValidationError('Описание вакансии должно быть не короче 10 символов.')
        return _validate_no_profanity(value, 'Описание вакансии')

    def validate_requirements(self, value):
        value = _normalize_text(value)
        if len(value) < 10:
            raise serializers.ValidationError('Требования к вакансии должны быть не короче 10 символов.')
        return _validate_no_profanity(value, 'Требования к вакансии')

    def validate_work_conditions_details(self, value):
        value = _normalize_text(value)
        if not value:
            return value
        return _validate_no_profanity(value, 'Детали условий работы')

    def validate_category(self, value):
        value = _normalize_text(value)
        if not value:
            raise serializers.ValidationError('Категория обязательна.')

        available_categories = get_available_vacancy_categories()
        if value not in available_categories:
            raise serializers.ValidationError(
                'Категория недоступна. Выберите категорию из списка или отправьте новую на модерацию.'
            )
        return value

    def validate_salary_min(self, value):
        return _validate_salary(value, 'Зарплата от')

    def validate_salary_max(self, value):
        return _validate_salary(value, 'Зарплата до')

    def validate(self, attrs):
        attrs = super().validate(attrs)

        salary_min = attrs.get('salary_min')
        salary_max = attrs.get('salary_max')
        if self.instance is not None:
            if salary_min is None:
                salary_min = self.instance.salary_min
            if salary_max is None:
                salary_max = self.instance.salary_max

        if salary_min is not None and salary_max is not None and salary_min > salary_max:
            raise serializers.ValidationError({
                'salary_min': 'Зарплата от не может быть больше зарплаты до.',
                'salary_max': 'Зарплата до должна быть не меньше зарплаты от.',
            })

        return attrs


class CompanyVacancySerializer(VacancyDetailSerializer):
    """
    Serializer for company cabinet vacancy CRUD.
    Company is set from authenticated user in viewset.perform_create().
    """

    class Meta(VacancyDetailSerializer.Meta):
        read_only_fields = ('company', 'created_date', 'views', 'is_archived')

class ComplaintSerializer(serializers.ModelSerializer):
    complainant_email = serializers.CharField(source='complainant.email', read_only=True)
    vacancy_position = serializers.CharField(source='vacancy.position', read_only=True)
    company_name = serializers.CharField(source='vacancy.company.name', read_only=True)
    
    class Meta:
        model = Complaint
        fields = '__all__'
        read_only_fields = ('complainant', 'created_at', 'resolved_at', 'status')


class AdminComplaintSerializer(serializers.ModelSerializer):
    """Админ сайта может менять статус и admin_notes."""

    complainant_email = serializers.CharField(source='complainant.email', read_only=True)
    vacancy_position = serializers.CharField(source='vacancy.position', read_only=True)
    company_name = serializers.CharField(source='vacancy.company.name', read_only=True)

    class Meta:
        model = Complaint
        fields = '__all__'
        read_only_fields = ('complainant', 'created_at', 'resolved_at')

# serializers.py
from rest_framework import serializers
from .models import Response, StatusResponse, Applicant, Vacancy

class ResponseSerializer(serializers.ModelSerializer):
    applicant_name = serializers.CharField(source='applicants.__str__', read_only=True)
    vacancy_position = serializers.CharField(source='vacancy.position', read_only=True)
    company_name = serializers.CharField(source='vacancy.company.name', read_only=True)
    status_name = serializers.CharField(source='status.status_response_name', read_only=True)
    vacancy_id = serializers.IntegerField(source='vacancy.id', read_only=True)
    company_id = serializers.IntegerField(source='vacancy.company.id', read_only=True)
    
    class Meta:
        model = Response
        fields = [
            'id',
            'applicant_name',
            'vacancy_position',
            'company_name',
            'status_name',
            'vacancy_id',
            'company_id',
            'response_date',
            'status',  # только для чтения в этом сериализаторе
            'applicants'  # только для чтения
        ]
        read_only_fields = [
            'id', 'response_date', 'status', 'applicants',
            'applicant_name', 'vacancy_position', 'company_name', 
            'status_name', 'vacancy_id', 'company_id'
        ]

class CreateResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Response
        fields = ['vacancy']  # Только эти поля можно отправлять
    
    def validate(self, data):
        user = self.context['request'].user
        
        if user.user_type != 'applicant':
            raise serializers.ValidationError("Только соискатели могут создавать отклики")
        
        try:
            applicant = user.applicant
        except Applicant.DoesNotExist:
            raise serializers.ValidationError("Профиль соискателя не найден")
        
        # Проверяем вакансию
        vacancy = data.get('vacancy')
        if not vacancy:
            raise serializers.ValidationError({"vacancy": "Вакансия обязательна"})
        
        # Проверяем, активна ли вакансия
        if hasattr(vacancy, 'is_active') and not vacancy.is_active:
            raise serializers.ValidationError("Нельзя откликнуться на неактивную вакансию")
        
        # Проверяем, не откликался ли уже
        if Response.objects.filter(applicants=applicant, vacancy=vacancy).exists():
            raise serializers.ValidationError("Вы уже откликались на эту вакансию")
        
        return data
    
    def create(self, validated_data):
        user = self.context['request'].user
        applicant = user.applicant
        
        # Получаем статус по умолчанию
        try:
            default_status = StatusResponse.objects.get(status_response_name="Отправлен")
        except StatusResponse.DoesNotExist:
            # Если нет статуса "Отправлен", берем первый доступный
            default_status = StatusResponse.objects.first()
            if not default_status:
                raise serializers.ValidationError("Нет доступных статусов отклика")
        
        # Создаем отклик
        response = Response.objects.create(
            applicants=applicant,
            status=default_status,
            **validated_data
        )
        return response

class CheckResponseSerializer(serializers.Serializer):
    has_responded = serializers.BooleanField()
    response_id = serializers.IntegerField(allow_null=True)
    status = serializers.CharField(allow_null=True)
    
    def to_representation(self, instance):
        """
        instance - это словарь с данными о отклике
        """
        return {
            'has_responded': instance['has_responded'],
            'response_id': instance['response_id'],
            'status': instance['status']
        }

class FavoritesSerializer(serializers.ModelSerializer):
    vacancy_details = VacancyListSerializer(source='vacancy', read_only=True)
    
    class Meta:
        model = Favorites
        fields = ('id', 'vacancy', 'vacancy_details', 'added_date')
        read_only_fields = ('added_date',)

class AdminLogSerializer(serializers.ModelSerializer):
    admin_username = serializers.CharField(source='admin.username', read_only=True)
    company_name = serializers.CharField(source='target_company.name', read_only=True)
    action_display = serializers.CharField(source='get_action_display', read_only=True)
    
    class Meta:
        model = AdminLog
        fields = '__all__'

class BackupSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    file_size_display = serializers.CharField(source='get_file_size_display', read_only=True)
    
    class Meta:
        model = Backup
        fields = '__all__'
        read_only_fields = ('file_size', 'created_at')


class BaseUserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ('email', 'username', 'phone', 'password', 'password2')

    def validate(self, attrs):
        attrs['email'] = (attrs.get('email') or '').strip().lower()
        attrs['username'] = (attrs.get('username') or attrs['email']).strip()

        normalized_phone = normalize_ru_phone(attrs.get('phone') or '')
        if not normalized_phone:
            raise serializers.ValidationError({
                'phone': 'Телефон должен быть в формате +7XXXXXXXXXX и содержать только цифры.'
            })
        attrs['phone'] = normalized_phone

        password = attrs.get('password') or ''
        if not re.search(r'[A-Za-z\u0400-\u04FF]', password):
            raise serializers.ValidationError({'password': 'Пароль должен содержать хотя бы одну букву.'})
        if not re.search(r'\d', password):
            raise serializers.ValidationError({'password': 'Пароль должен содержать хотя бы одну цифру.'})

        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({'password': 'Пароли не совпадают'})
        return attrs

# Регистрация соискателя
class ApplicantRegistrationSerializer(BaseUserRegistrationSerializer):
    first_name = serializers.CharField(max_length=80)
    last_name = serializers.CharField(max_length=80)
    birth_date = serializers.DateField()
    resume = serializers.CharField(required=False, allow_blank=True)
    resume_file = serializers.FileField(
        required=False,
        allow_null=True,
        validators=[FileExtensionValidator(RESUME_FILE_ALLOWED_EXTENSIONS)],
    )
    
    class Meta(BaseUserRegistrationSerializer.Meta):
        fields = BaseUserRegistrationSerializer.Meta.fields + (
            'first_name', 'last_name', 'birth_date', 'resume', 'resume_file'
        )

    def validate_first_name(self, value):
        return _validate_person_name(value, 'Имя')

    def validate_last_name(self, value):
        return _validate_person_name(value, 'Фамилия')

    def validate_birth_date(self, value):
        return _validate_birth_date(value)

    def validate_resume(self, value):
        if value is None:
            return value
        value = _normalize_text(value)
        if not value:
            return value
        return _validate_no_profanity(value, 'Резюме')

    def validate_resume_file(self, value):
        return _validate_resume_file(value)
    
    def create(self, validated_data):
        # Извлекаем данные для Applicant
        first_name = validated_data.pop('first_name')
        last_name = validated_data.pop('last_name')
        applicant_data = {
            'first_name': first_name,
            'last_name': last_name,
            'birth_date': validated_data.pop('birth_date'),
            'resume': validated_data.pop('resume', ''),
            'resume_file': validated_data.pop('resume_file', None),
        }
        
        # Создаем пользователя
        validated_data.pop('password2')
        validated_data['user_type'] = 'applicant'
        validated_data['first_name'] = first_name
        validated_data['last_name'] = last_name
        user = User.objects.create_user(**validated_data)
        
        # Создаем Applicant
        Applicant.objects.create(user=user, **applicant_data)
        
        return user

# Регистрация компании
class CompanyRegistrationSerializer(BaseUserRegistrationSerializer):
    name = serializers.CharField(max_length=100)
    number = serializers.CharField(max_length=10)
    industry = serializers.CharField(max_length=100)
    description = serializers.CharField()
    verification_document = serializers.FileField(
        validators=[FileExtensionValidator(['pdf'])]
    )

    class Meta(BaseUserRegistrationSerializer.Meta):
        fields = BaseUserRegistrationSerializer.Meta.fields + (
            'name', 'number', 'industry', 'description', 'verification_document'
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Allow re-submission flow for rejected companies.
        for field_name in ('email', 'username'):
            field = self.fields.get(field_name)
            if not field:
                continue
            field.validators = [
                validator for validator in field.validators
                if not isinstance(validator, UniqueValidator)
            ]

    def validate(self, attrs):
        attrs = super().validate(attrs)

        username_taken = (
            User.objects
            .filter(username=attrs['username'])
            .exclude(email=attrs['email'])
            .exists()
        )
        if username_taken:
            raise serializers.ValidationError({
                'username': 'Пользователь с таким username уже существует.'
            })

        existing_user = User.objects.filter(email=attrs['email']).first()
        if not existing_user:
            return attrs

        company = getattr(existing_user, 'company', None)
        if existing_user.user_type != 'company' or not company:
            raise serializers.ValidationError({
                'email': 'Пользователь с таким email уже существует.'
            })

        if company.status != Company.STATUS_REJECTED:
            status_display = dict(Company.STATUS_CHOICES).get(company.status, company.status)
            raise serializers.ValidationError({
                'email': (
                    f'Компания с этим email уже зарегистрирована (статус: {status_display}). '
                    'Повторная отправка доступна только для отклоненной компании.'
                )
            })

        attrs['_rejected_company_user'] = existing_user
        return attrs

    def validate_name(self, value):
        value = _normalize_text(value)
        if len(value) < 2:
            raise serializers.ValidationError('Название компании слишком короткое.')
        if not COMPANY_NAME_RE.fullmatch(value):
            raise serializers.ValidationError(
                'В названии компании допустимы буквы, цифры, пробелы и знаки: . , - & ( )'
            )
        return _validate_no_profanity(value, 'Название компании')

    def validate_number(self, value):
        value = (value or '').strip()
        if not value.isdigit():
            raise serializers.ValidationError('ИНН должен содержать только цифры.')
        if len(value) != 10:
            raise serializers.ValidationError('ИНН должен содержать ровно 10 цифр.')
        return value

    def validate_industry(self, value):
        value = _normalize_text(value)
        if len(value) < 2:
            raise serializers.ValidationError('Сфера деятельности слишком короткая.')
        if not INDUSTRY_RE.fullmatch(value):
            raise serializers.ValidationError('Поле сферы деятельности содержит недопустимые символы.')
        return _validate_no_profanity(value, 'Сфера деятельности')

    def validate_description(self, value):
        value = _normalize_text(value)
        if len(value) < 10:
            raise serializers.ValidationError('Описание должно быть не короче 10 символов.')
        return _validate_no_profanity(value, 'Описание компании')

    def validate_verification_document(self, value):
        max_size = 5 * 1024 * 1024
        if value.size > max_size:
            raise serializers.ValidationError('Размер PDF не должен превышать 5 МБ.')
        return value

    def create(self, validated_data):
        rejected_user = validated_data.pop('_rejected_company_user', None)
        company_data = {
            'name': validated_data.pop('name'),
            'number': validated_data.pop('number'),
            'industry': validated_data.pop('industry'),
            'description': validated_data.pop('description'),
            'verification_document': validated_data.pop('verification_document')
        }

        raw_password = validated_data.pop('password')
        validated_data.pop('password2')

        if rejected_user:
            rejected_user.phone = validated_data.get('phone', rejected_user.phone)
            rejected_user.user_type = 'company'
            rejected_user.is_active = True
            if not rejected_user.username:
                rejected_user.username = validated_data.get('username') or rejected_user.email
                rejected_user.save(update_fields=['phone', 'user_type', 'is_active', 'username'])
            else:
                rejected_user.save(update_fields=['phone', 'user_type', 'is_active'])

            rejected_user.set_password(raw_password)
            rejected_user.save(update_fields=['password'])

            company = rejected_user.company
            company.name = company_data['name']
            company.number = company_data['number']
            company.industry = company_data['industry']
            company.description = company_data['description']
            company.verification_document = company_data['verification_document']
            company.status = Company.STATUS_PENDING

            update_fields = [
                'name', 'number', 'industry', 'description',
                'verification_document', 'status'
            ]
            if hasattr(company, 'admin_notes'):
                company.admin_notes = ''
                update_fields.append('admin_notes')
            company.save(update_fields=update_fields)
            return rejected_user

        validated_data['password'] = raw_password
        validated_data['user_type'] = 'company'
        user = User.objects.create_user(**validated_data)
        Company.objects.create(user=user, **company_data)

        return user
class EmployeeRegistrationSerializer(BaseUserRegistrationSerializer):
    first_name = serializers.CharField(max_length=80)
    last_name = serializers.CharField(max_length=80)
    role = serializers.ChoiceField(choices=[
        ('hr', 'HR \u0430\u0433\u0435\u043d\u0442'),
        ('content_manager', '\u041a\u043e\u043d\u0442\u0435\u043d\u0442-\u043c\u0435\u043d\u0435\u0434\u0436\u0435\u0440'),
        ('site_admin', '\u0410\u0434\u043c\u0438\u043d\u0438\u0441\u0442\u0440\u0430\u0442\u043e\u0440 \u0441\u0430\u0439\u0442\u0430'),
    ])
    company_id = serializers.IntegerField(required=False, allow_null=True)
    
    class Meta(BaseUserRegistrationSerializer.Meta):
        fields = BaseUserRegistrationSerializer.Meta.fields + (
            'first_name', 'last_name', 'role', 'company_id'
        )

    def validate_first_name(self, value):
        return _validate_person_name(value, 'Имя')

    def validate_last_name(self, value):
        return _validate_person_name(value, 'Фамилия')
    
    def validate(self, attrs):
        attrs = super().validate(attrs)
        
        # Для сотрудников компании (HR/Content Manager) компания обязательна
        if attrs.get('role') in ['hr', 'content_manager'] and not attrs.get('company_id'):
            raise serializers.ValidationError({
                "company_id": "Для HR-агента необходимо указать компанию"
            })
        
        return attrs
    
    def create(self, validated_data):
        # Извлекаем данные для Employee
        first_name = validated_data.pop('first_name')
        last_name = validated_data.pop('last_name')
        role = validated_data.pop('role')
        
        company_id = validated_data.pop('company_id', None)
        
        # Создаем пользователя
        validated_data.pop('password2')
        # user_type для сотрудников — staff, для админа сайта — adminsite
        validated_data['user_type'] = 'adminsite' if role == 'site_admin' else 'staff'
        user = User.objects.create_user(**validated_data)
        
        company = None
        if company_id:
            try:
                company = Company.objects.get(id=company_id)
            except Company.DoesNotExist:
                raise serializers.ValidationError({"company_id": "Компания не найдена"})

        # Создаем Employee
        employee = Employee.objects.create(user=user, company=company, role=role)
        # Дублируем ФИО в User (удобно для админки/чата)
        user.first_name = first_name
        user.last_name = last_name
        user.save(update_fields=['first_name', 'last_name'])
        return user

# Сериализатор для отображения пользователя
class UserSerializer(serializers.ModelSerializer):
    user_type_display = serializers.CharField(source='get_user_type_display', read_only=True)
    
    class Meta:
        model = User
        fields = ('id', 'email', 'username', 'phone', 'user_type', 
                 'user_type_display', 'first_name', 'last_name', 'date_joined')
        read_only_fields = ('id', 'date_joined')

# Детальный сериализатор с информацией о профиле
class UserProfileSerializer(serializers.ModelSerializer):
    # Поля из User
    id = serializers.IntegerField(read_only=True)
    username = serializers.CharField(read_only=True)
    email = serializers.EmailField(required=False)
    user_type = serializers.CharField(read_only=True)
    user_type_display = serializers.CharField(source='get_user_type_display', read_only=True)
    employee_role = serializers.SerializerMethodField(read_only=True)
    company_id = serializers.SerializerMethodField(read_only=True)
    company_name = serializers.SerializerMethodField(read_only=True)
    company_number = serializers.SerializerMethodField(read_only=True)
    company_industry = serializers.SerializerMethodField(read_only=True)
    company_description = serializers.SerializerMethodField(read_only=True)

    # Поля, которые можно редактировать
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)
    phone = serializers.CharField(required=False, allow_blank=True)

    # Поля из Applicant (только для соискателей)
    applicant_id = serializers.SerializerMethodField(read_only=True)
    birth_date = serializers.DateField(source='applicant.birth_date', required=False, allow_null=True)
    resume = serializers.CharField(source='applicant.resume', required=False, allow_blank=True, allow_null=True)
    resume_file = serializers.FileField(
        source='applicant.resume_file',
        required=False,
        allow_null=True,
        validators=[FileExtensionValidator(RESUME_FILE_ALLOWED_EXTENSIONS)],
    )
    avatar = serializers.ImageField(source='applicant.avatar', required=False, allow_null=True)
    # theme = serializers.CharField(source='applicant.theme', required=False, allow_blank=True)  # если есть

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'phone', 'user_type', 'user_type_display',
            'first_name', 'last_name',
            'applicant_id', 'birth_date', 'resume', 'resume_file', 'avatar',
            'employee_role', 'company_id',
            'company_name', 'company_number', 'company_industry', 'company_description',
        ]
        read_only_fields = ('id', 'username', 'user_type', 'user_type_display', 'applicant_id')

    def get_applicant_id(self, obj):
        try:
            return obj.applicant.id
        except Applicant.DoesNotExist:
            return None
        
    def get_employee_role(self, obj):
        try:
            return obj.employee.role
        except Employee.DoesNotExist:
            return None

    def get_company_id(self, obj):
        try:
            emp = obj.employee
            return emp.company_id
        except Employee.DoesNotExist:
            return None

    def get_company_name(self, obj):
        try:
            company = obj.employee.company
            return company.name if company else None
        except Employee.DoesNotExist:
            return None

    def get_company_number(self, obj):
        try:
            company = obj.employee.company
            return company.number if company else None
        except Employee.DoesNotExist:
            return None

    def get_company_industry(self, obj):
        try:
            company = obj.employee.company
            return company.industry if company else None
        except Employee.DoesNotExist:
            return None

    def get_company_description(self, obj):
        try:
            company = obj.employee.company
            return company.description if company else None
        except Employee.DoesNotExist:
            return None

    def to_representation(self, instance):
        data = super().to_representation(instance)

        if instance.user_type == 'applicant':
            try:
                applicant = instance.applicant
                if not data.get('first_name') and applicant.first_name:
                    data['first_name'] = applicant.first_name
                if not data.get('last_name') and applicant.last_name:
                    data['last_name'] = applicant.last_name
            except Applicant.DoesNotExist:
                pass

        return data

    def validate_first_name(self, value):
        if value == '':
            return value
        return _validate_person_name(value, 'Имя')

    def validate_last_name(self, value):
        if value == '':
            return value
        return _validate_person_name(value, 'Фамилия')

    def validate_phone(self, value):
        value = (value or '').strip()
        if not value:
            return value
        normalized = normalize_ru_phone(value)
        if not normalized:
            raise serializers.ValidationError(
                'Телефон должен быть в формате +7XXXXXXXXXX и содержать только цифры.'
            )
        return normalized

    def validate_birth_date(self, value):
        if value is None:
            return value
        return _validate_birth_date(value)

    def validate_resume(self, value):
        value = _normalize_text(value)
        if not value:
            return value
        return _validate_no_profanity(value, 'Резюме')

    def validate_resume_file(self, value):
        return _validate_resume_file(value)

    def update(self, instance, validated_data):
        applicant_data = validated_data.pop('applicant', {})

        # Update User fields
        if 'email' in validated_data:
            instance.email = validated_data.get('email')
        instance.first_name = validated_data.get('first_name', instance.first_name)
        instance.last_name = validated_data.get('last_name', instance.last_name)
        instance.phone = validated_data.get('phone', instance.phone)
        instance.save()

        # Update linked Applicant fields
        if instance.user_type == 'applicant':
            try:
                applicant = instance.applicant
                if 'first_name' in validated_data:
                    applicant.first_name = validated_data['first_name']
                if 'last_name' in validated_data:
                    applicant.last_name = validated_data['last_name']
                for attr, value in applicant_data.items():
                    setattr(applicant, attr, value)
                applicant.save()
            except Applicant.DoesNotExist:
                if applicant_data.get('birth_date'):
                    Applicant.objects.create(
                        user=instance,
                        first_name=validated_data.get('first_name', ''),
                        last_name=validated_data.get('last_name', ''),
                        **applicant_data,
                    )

        return instance


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True, min_length=8)
    new_password = serializers.CharField(write_only=True, min_length=8)
    new_password_confirm = serializers.CharField(write_only=True, min_length=8)

    def validate(self, attrs):
        user = self.context['request'].user

        old_password = attrs.get('old_password')
        new_password = attrs.get('new_password')
        new_password_confirm = attrs.get('new_password_confirm')

        if not user.check_password(old_password):
            raise serializers.ValidationError({'old_password': 'Неверный текущий пароль'})

        if new_password != new_password_confirm:
            raise serializers.ValidationError({'new_password_confirm': 'Пароли не совпадают'})

        if old_password == new_password:
            raise serializers.ValidationError({'new_password': 'Новый пароль должен отличаться от текущего'})

        validate_password(new_password, user=user)
        return attrs
    
# serializers.py
class ChatSerializer(serializers.ModelSerializer):
    vacancy_title = serializers.CharField(source='vacancy.position', read_only=True)
    company_name = serializers.CharField(source='company.name', read_only=True)
    applicant_name = serializers.CharField(source='applicant.__str__', read_only=True)
    
    # Информация о вакансии
    vacancy_info = serializers.SerializerMethodField()
    
    # Информация о соискателе
    applicant_info = serializers.SerializerMethodField()
    
    # Кто может писать в чат (сотрудники компании)
    company_users = serializers.SerializerMethodField()
    
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    is_archived = serializers.SerializerMethodField()
    
    class Meta:
        model = Chat
        fields = [
            'id', 'vacancy', 'vacancy_title', 'vacancy_info',
            'company', 'company_name', 'company_users',
            'applicant', 'applicant_name', 'applicant_info',
            'created_at', 'last_message_at', 'last_message',
            'unread_count', 'is_active', 'is_archived',
            'is_archived_by_applicant', 'is_archived_by_company',
        ]
        read_only_fields = [
            'created_at',
            'last_message_at',
            'is_archived',
            'is_archived_by_applicant',
            'is_archived_by_company',
        ]
    
    def get_vacancy_info(self, obj):
        return {
            'id': obj.vacancy.id,
            'position': obj.vacancy.position,
            'salary_min': obj.vacancy.salary_min,
            'salary_max': obj.vacancy.salary_max,
            'city': obj.vacancy.city,
        }
    
    def get_applicant_info(self, obj):
        return {
            'id': obj.applicant.id,
            'full_name': f"{obj.applicant.first_name} {obj.applicant.last_name}",
            'email': obj.applicant.user.email,
            'phone': obj.applicant.user.phone,
        }
    
    def get_company_users(self, obj):
        """Сотрудники компании, которые могут писать в чат"""
        # Все сотрудники компании + сама компания (user)
        users = []
        
        # Добавляем пользователя компании
        if obj.company.user:
            users.append({
                'id': obj.company.user.id,
                'email': obj.company.user.email,
                'name': obj.company.name,
                'type': 'company_owner'
            })
        
        # Добавляем сотрудников
        employees = Employee.objects.filter(company=obj.company)
        for emp in employees:
            if emp.user:
                users.append({
                    'id': emp.user.id,
                    'email': emp.user.email,
                    'name': f"{emp.user.first_name} {emp.user.last_name}",
                    'type': emp.user.user_type
                })
        
        return users
    
    def get_last_message(self, obj):
        last_msg = obj.messages.last()
        if last_msg:
            return {
                'text': last_msg.text[:100] + ('...' if len(last_msg.text) > 100 else ''),
                'sender_type': last_msg.sender_type,
                'created_at': last_msg.created_at
            }
        return None
    
    def get_unread_count(self, obj):
        user = self.context['request'].user
        
        if user.user_type == 'applicant':
            # Для соискателя - непрочитанные сообщения от компании
            return obj.messages.filter(
                sender_type='company',
                is_read_by_applicant=False
            ).count()
        else:
            # Для компании - непрочитанные сообщения от соискателя
            return obj.messages.filter(
                sender_type='applicant',
                is_read_by_company=False
            ).count()

    def get_is_archived(self, obj):
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if not user or not user.is_authenticated:
            return False

        if user.user_type == 'applicant':
            return bool(obj.is_archived_by_applicant)
        if user.user_type in ('company', 'staff'):
            return bool(obj.is_archived_by_company)
        if user.user_type == 'adminsite' or user.is_superuser:
            return bool(obj.is_archived_by_company or obj.is_archived_by_applicant)
        return False
        

class MessageSerializer(serializers.ModelSerializer):
    sender_email = serializers.CharField(source='sender.email', read_only=True)
    sender_name = serializers.SerializerMethodField()
    is_my_message = serializers.SerializerMethodField()
    
    class Meta:
        model = Message
        fields = [
            'id', 'text', 'sender_email', 'sender_name',
            'is_my_message', 'is_read', 'created_at'
        ]
        read_only_fields = ['created_at']
    
    def get_sender_name(self, obj):
        sender = obj.sender
        if hasattr(sender, 'applicant'):
            return f"{sender.applicant.first_name} {sender.applicant.last_name}"
        elif hasattr(sender, 'company'):
            return sender.company.name
        return sender.email
    
    def get_is_my_message(self, obj):
        return obj.sender == self.context['request'].user

class SendMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ['text']

    def validate_text(self, value):
        value = _normalize_text(value)
        if not value:
            raise serializers.ValidationError('Сообщение не может быть пустым.')
        return _validate_no_profanity(value, 'Сообщение')
    
    def create(self, validated_data):
        return Message.objects.create(**validated_data)

class VacancyShortSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source='company.name', read_only=True)
    has_applied = serializers.SerializerMethodField()

    class Meta:
        model = Vacancy
        fields = (
            'id',
            'position',
            'salary_min',
            'salary_max',
            'city',
            'company_name',
            'has_applied',
        )

    def get_has_applied(self, obj):
        request = self.context.get("request")
        if not request or not request.user or not request.user.is_authenticated:
            return False

        try:
            applicant = request.user.applicant
        except Applicant.DoesNotExist:
            return False

        return Response.objects.filter(applicants=applicant, vacancy=obj).exists()

class VacancyVideoFeedSerializer(serializers.ModelSerializer):
    vacancy = VacancyShortSerializer(read_only=True)

    likes_count = serializers.SerializerMethodField()
    is_liked = serializers.SerializerMethodField()

    class Meta:
        model = VacancyVideo
        fields = (
            'id',
            'video',
            'description',
            'created_at',
            'vacancy',
            'likes_count',
            'is_liked',
        )

    def get_likes_count(self, obj):
        return obj.vacancyvideolike_set.count()

    def get_is_liked(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False

        try:
            applicant = request.user.applicant
        except:
            return False

        return obj.vacancyvideolike_set.filter(applicant=applicant).exists()



from rest_framework import serializers
from .models import VacancyVideo
from .utils import validate_video

class VacancyVideoAdminSerializer(serializers.ModelSerializer):

    class Meta:
        model = VacancyVideo
        fields = (
            'id',
            'vacancy',
            'video',
            'description',
            'is_active',
        )
        read_only_fields = ('is_active',)

    def validate_vacancy(self, value):
        instance_id = self.instance.id if self.instance else None
        return _validate_vacancy_video_capacity(value, exclude_video_id=instance_id)

    def create(self, validated_data):
        # uploaded_by/company приходят из viewset.perform_create(serializer.save(...))
        # поэтому тут просто создаём модель без дублей kwargs.
        instance = VacancyVideo.objects.create(**validated_data)

        errors = validate_video(
            instance.video.path,
            instance.video.size
        )

        instance.is_active = (not errors)
        instance.save(update_fields=['is_active'])

        return instance

class ContentManagerCreateSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(max_length=80)
    last_name = serializers.CharField(max_length=80)
    email = serializers.EmailField(write_only=True)
    password = serializers.CharField(write_only=True)

    company_id = serializers.IntegerField(write_only=True)  # ✅ ДОБАВЬ

    class Meta:
        model = Employee
        fields = ('email', 'password', 'first_name', 'last_name', 'company_id')  # ✅ ДОБАВЬ

    def validate_first_name(self, value):
        return _validate_person_name(value, 'Имя')

    def validate_last_name(self, value):
        return _validate_person_name(value, 'Фамилия')

    def create(self, validated_data):
        company = Company.objects.get(id=validated_data["company_id"])

        user = User.objects.create_user(
            username=validated_data['email'],
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
            user_type='staff'
        )

        return Employee.objects.create(
            user=user,
            role='content_manager',
            company=company
        )



class ContentManagerVideoSerializer(serializers.ModelSerializer):
    # отдаём нормальный URL на файл
    video = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = VacancyVideo
        fields = ('id', 'vacancy', 'video', 'description', 'is_active')
        read_only_fields = ('id', 'video', 'is_active')

    def get_video(self, obj):
        request = self.context.get("request")
        if obj.video and hasattr(obj.video, "url"):
            return request.build_absolute_uri(obj.video.url) if request else obj.video.url
        return None

    def validate_description(self, value):
        value = _normalize_text(value)
        if not value:
            return value
        return _validate_no_profanity(value, 'Описание видео')

    def validate_vacancy(self, value):
        user = self.context['request'].user

        if not hasattr(user, 'employee') or user.employee.role != 'content_manager':
            raise serializers.ValidationError("Только контент-менеджер может добавлять видео")

        if value.company != user.employee.company:
            raise serializers.ValidationError("Нельзя загружать видео для чужой компании")

        instance_id = self.instance.id if self.instance else None
        return _validate_vacancy_video_capacity(value, exclude_video_id=instance_id)

    def create(self, validated_data):
        request = self.context['request']

        # video файл берётся из request.FILES (MultiPartParser)
        video_file = request.FILES.get("video")
        if not video_file:
            raise serializers.ValidationError({"video": "Файл видео обязателен"})

        # uploaded_by/company приходят из viewset.perform_create(serializer.save(...))
        # тут добавляем только сам файл.
        instance = VacancyVideo.objects.create(video=video_file, **validated_data)

        # если хочешь модерацию — оставь False и убери автоактивацию
        # но я оставляю твою логику: валидное видео -> active True
        try:
            errors = validate_video(instance.video.path, instance.video.size)
        except Exception:
            errors = ["validate_error"]

        instance.is_active = (not errors)
        instance.save(update_fields=['is_active'])
        return instance


class ContentManagerVideoListSerializer(serializers.ModelSerializer):
    video = serializers.SerializerMethodField(read_only=True)
    vacancy_position = serializers.CharField(source='vacancy.position', read_only=True)
    likes_count = serializers.SerializerMethodField()
    views_count = serializers.SerializerMethodField()

    class Meta:
        model = VacancyVideo
        fields = (
            'id', 'video', 'description',
            'vacancy', 'vacancy_position',
            'likes_count', 'views_count',
            'is_active'
        )

    def get_video(self, obj):
        request = self.context.get("request")
        if obj.video and hasattr(obj.video, "url"):
            return request.build_absolute_uri(obj.video.url) if request else obj.video.url
        return None

    def get_likes_count(self, obj):
        return obj.vacancyvideolike_set.count()

    def get_views_count(self, obj):
        return obj.vacancyvideoview_set.count()
    

class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

class PasswordResetConfirmSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(min_length=6, max_length=6)
    new_password = serializers.CharField(min_length=8)

    def validate(self, attrs):
        email = attrs["email"].strip().lower()
        code = attrs["code"].strip()

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError({"email": "Пользователь не найден"})

        prc = (PasswordResetCode.objects
               .filter(user=user, code=code, is_used=False, expires_at__gt=timezone.now())
               .order_by("-created_at")
               .first())

        if not prc:
            raise serializers.ValidationError({"code": "Неверный или просроченный код"})

        attrs["user"] = user
        attrs["reset_obj"] = prc
        return attrs


# -------------------- Company staff management --------------------

class CompanyEmployeeCreateSerializer(serializers.Serializer):
    """Создание HR-агента/контент-менеджера владельцем компании."""

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    first_name = serializers.CharField(max_length=80)
    last_name = serializers.CharField(max_length=80)
    role = serializers.ChoiceField(choices=[
        ('hr', 'HR \u0430\u0433\u0435\u043d\u0442'),
        ('content_manager', '\u041a\u043e\u043d\u0442\u0435\u043d\u0442-\u043c\u0435\u043d\u0435\u0434\u0436\u0435\u0440'),
    ])

    def validate_first_name(self, value):
        return _validate_person_name(value, 'Имя')

    def validate_last_name(self, value):
        return _validate_person_name(value, 'Фамилия')

    def validate_password(self, value):
        if not re.search(r'[A-Za-z\u0400-\u04FF]', value):
            raise serializers.ValidationError('Пароль должен содержать хотя бы одну букву.')
        if not re.search(r'\d', value):
            raise serializers.ValidationError('Пароль должен содержать хотя бы одну цифру.')
        return value

    def create(self, validated_data):
        request = self.context['request']
        owner = request.user
        if owner.user_type != 'company':
            raise serializers.ValidationError('Только владелец компании может создавать сотрудников')

        company = owner.company

        user = User.objects.create_user(
            username=validated_data['email'],
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
            phone='',
            user_type='staff',
        )

        employee = Employee.objects.create(
            user=user,
            company=company,
            role=validated_data['role'],
        )
        return employee


class CompanyEmployeeListSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source='user.email', read_only=True)
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)
    is_active = serializers.BooleanField(source='user.is_active', read_only=True)

    class Meta:
        model = Employee
        fields = ('id', 'email', 'first_name', 'last_name', 'role', 'company', 'is_active')


class CompanyEmployeeUpdateSerializer(serializers.Serializer):
    first_name = serializers.CharField(required=False, allow_blank=True, max_length=80)
    last_name = serializers.CharField(required=False, allow_blank=True, max_length=80)
    role = serializers.ChoiceField(required=False, choices=[
        ('hr', 'HR \u0430\u0433\u0435\u043d\u0442'),
        ('content_manager', '\u041a\u043e\u043d\u0442\u0435\u043d\u0442-\u043c\u0435\u043d\u0435\u0434\u0436\u0435\u0440'),
    ])
    is_active = serializers.BooleanField(required=False)

    def validate_first_name(self, value):
        if value == '':
            return value
        return _validate_person_name(value, 'Имя')

    def validate_last_name(self, value):
        if value == '':
            return value
        return _validate_person_name(value, 'Фамилия')

    def update(self, instance, validated_data):
        # instance: Employee
        user = instance.user
        if 'first_name' in validated_data:
            user.first_name = validated_data['first_name']
        if 'last_name' in validated_data:
            user.last_name = validated_data['last_name']
        if 'is_active' in validated_data:
            user.is_active = validated_data['is_active']
        user.save(update_fields=['first_name', 'last_name', 'is_active'])

        if 'role' in validated_data:
            instance.role = validated_data['role']
            instance.save(update_fields=['role'])
        return instance
