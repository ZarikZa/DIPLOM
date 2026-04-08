import os
from django.contrib.auth.models import AbstractUser
from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=80)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'phone']

    USER_TYPE_CHOICES = (
        ('applicant', 'Соискатель'),
        ('company', 'Компания'),
        ('analitic', 'Аналитик'),
        ('hragent', 'HR агент'),
        ('adminsite', 'Администратор сайта'),
    )
    user_type = models.CharField(max_length=20, choices=USER_TYPE_CHOICES, default='applicant')

    class Meta:
        db_table = 'users'
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        if not self.username:
            self.username = self.email
        super().save(*args, **kwargs)


class Role(models.Model):
    role_name = models.CharField(max_length=100)

    class Meta:
        db_table = 'roles'
        verbose_name = 'Роль'
        verbose_name_plural = 'Роли'

    def __str__(self):
        return self.role_name


class Company(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'На проверке'),
        (STATUS_APPROVED, 'Подтверждена'),
        (STATUS_REJECTED, 'Отклонена'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    number = models.CharField(max_length=10)
    industry = models.CharField(max_length=100)
    description = models.TextField()
    theme = models.CharField(max_length=100, blank=True, null=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        verbose_name='Статус аккаунта',
    )
    verification_document = models.FileField(
        upload_to='company_documents/%Y/%m/%d/',
        verbose_name='Подтверждающий документ (PDF)',
        validators=[FileExtensionValidator(['pdf'])],
        help_text='Загрузите документ в формате PDF',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'companies'
        verbose_name = 'Компания'
        verbose_name_plural = 'Компании'

    def __str__(self):
        return self.name

    def is_approved(self):
        return self.status == self.STATUS_APPROVED


class Applicant(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80)
    birth_date = models.DateField()
    resume = models.TextField(blank=True)
    theme = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        db_table = 'applicants'
        verbose_name = 'Соискатель'
        verbose_name_plural = 'Соискатели'

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    def add_to_favorites(self, vacancy):
        favorite, created = Favorites.objects.get_or_create(
            applicant=self,
            vacancy=vacancy,
        )
        return created

    def remove_from_favorites(self, vacancy):
        Favorites.objects.filter(applicant=self, vacancy=vacancy).delete()

    def get_favorites(self):
        return self.favorite_vacancies.all()

    def is_in_favorites(self, vacancy):
        return Favorites.objects.filter(applicant=self, vacancy=vacancy).exists()


class Employee(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True)
    access_level = models.CharField(max_length=50, default='standard')
    theme = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        db_table = 'employees'
        verbose_name = 'Сотрудник'
        verbose_name_plural = 'Сотрудники'

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class WorkConditions(models.Model):
    work_conditions_name = models.CharField(max_length=50)

    class Meta:
        db_table = 'work_conditions'
        verbose_name = 'Условие работы'
        verbose_name_plural = 'Условия работы'

    def __str__(self):
        return self.work_conditions_name


class StatusVacancies(models.Model):
    status_vacancies_name = models.CharField(max_length=50)

    class Meta:
        db_table = 'status_vacancies'
        verbose_name = 'Статус вакансии'
        verbose_name_plural = 'Статусы вакансий'

    def __str__(self):
        return self.status_vacancies_name


class StatusResponse(models.Model):
    status_response_name = models.CharField(max_length=100)

    class Meta:
        db_table = 'status_responses'
        verbose_name = 'Статус отклика'
        verbose_name_plural = 'Статусы откликов'

    def __str__(self):
        return self.status_response_name


class Vacancy(models.Model):
    company = models.ForeignKey('Company', on_delete=models.CASCADE)
    work_conditions = models.ForeignKey('WorkConditions', on_delete=models.CASCADE)
    position = models.CharField(max_length=100)
    description = models.TextField()
    requirements = models.TextField()
    salary_min = models.DecimalField(max_digits=12, decimal_places=2)
    salary_max = models.DecimalField(max_digits=12, decimal_places=2)
    created_date = models.DateTimeField(auto_now_add=True)
    status = models.ForeignKey('StatusVacancies', on_delete=models.CASCADE)
    views = models.PositiveIntegerField(default=0)
    experience = models.CharField(
        max_length=20,
        choices=[
            ('Без опыта', 'Без опыта'),
            ('1-3 года', '1-3 года'),
            ('3-6 лет', '3-6 лет'),
            ('от 6 лет', 'от 6 лет'),
        ],
        blank=True,
        null=True,
    )
    city = models.CharField(max_length=100, default='Москва')
    category = models.CharField(
        max_length=50,
        choices=[
            ('IT', 'IT'),
            ('Маркетинг', 'Маркетинг'),
            ('Продажи', 'Продажи'),
            ('HR', 'HR'),
        ],
        default='IT',
    )
    work_conditions_details = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'vacancies'
        verbose_name = 'Вакансия'
        verbose_name_plural = 'Вакансии'

    def __str__(self):
        return f"{self.position} - {self.company.name}"


class Complaint(models.Model):
    COMPLAINT_TYPES = [
        ('spam', 'Спам'),
        ('fraud', 'Мошенничество'),
        ('inappropriate', 'Неуместный контент'),
        ('discrimination', 'Дискриминация'),
        ('false_info', 'Ложная информация'),
        ('other', 'Другое'),
    ]

    STATUS_CHOICES = [
        ('pending', 'На рассмотрении'),
        ('reviewed', 'Рассмотрено'),
        ('rejected', 'Отклонено'),
        ('resolved', 'Решено'),
    ]

    vacancy = models.ForeignKey(Vacancy, on_delete=models.CASCADE, verbose_name='Вакансия')
    complainant = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='Подавший жалобу')
    complaint_type = models.CharField(max_length=50, choices=COMPLAINT_TYPES, verbose_name='Тип жалобы')
    description = models.TextField(verbose_name='Описание проблемы', blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='Статус')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    resolved_at = models.DateTimeField(null=True, blank=True, verbose_name='Дата решения')
    admin_notes = models.TextField(blank=True, verbose_name='Заметки администратора')

    class Meta:
        db_table = 'complaints'
        verbose_name = 'Жалоба'
        verbose_name_plural = 'Жалобы'
        unique_together = ['vacancy', 'complainant']

    def __str__(self):
        return f"Жалоба на {self.vacancy.position} от {self.complainant.email}"

    def save(self, *args, **kwargs):
        if self.status != 'pending' and not self.resolved_at:
            self.resolved_at = timezone.now()
        super().save(*args, **kwargs)


class Response(models.Model):
    applicants = models.ForeignKey(Applicant, on_delete=models.CASCADE)
    vacancy = models.ForeignKey(Vacancy, on_delete=models.CASCADE)
    response_date = models.DateTimeField(auto_now_add=True)
    status = models.ForeignKey(StatusResponse, on_delete=models.CASCADE)

    class Meta:
        db_table = 'responses'
        verbose_name = 'Отклик'
        verbose_name_plural = 'Отклики'
        unique_together = ['applicants', 'vacancy']

    def __str__(self):
        return f"Отклик {self.applicants} на {self.vacancy}"


class Favorites(models.Model):
    applicant = models.ForeignKey(Applicant, on_delete=models.CASCADE, verbose_name='Соискатель')
    vacancy = models.ForeignKey(Vacancy, on_delete=models.CASCADE, verbose_name='Вакансия')
    added_date = models.DateTimeField(auto_now_add=True, verbose_name='Дата добавления')

    class Meta:
        db_table = 'favorites'
        verbose_name = 'Избранное'
        verbose_name_plural = 'Избранные вакансии'
        unique_together = ['applicant', 'vacancy']

    def __str__(self):
        return f"{self.applicant} - {self.vacancy}"


class ActionType(models.Model):
    """Action type for admin logging."""

    code = models.CharField(max_length=50, unique=True, verbose_name='Code')
    name = models.CharField(max_length=100, verbose_name='Name')
    description = models.TextField(blank=True, verbose_name='Description')

    class Meta:
        db_table = 'apihh_main_actiontype'
        verbose_name = 'Action type'
        verbose_name_plural = 'Action types'

    def __str__(self):
        return self.name


class AdminLog(models.Model):
    admin = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='User')
    action = models.ForeignKey(ActionType, on_delete=models.CASCADE, verbose_name='Action')
    target_company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name='Target company',
    )
    target_object_id = models.PositiveIntegerField(null=True, blank=True, verbose_name='Target object ID')
    target_content_type = models.CharField(max_length=100, blank=True, verbose_name='Target content type')
    details = models.TextField(blank=True, verbose_name='Details')
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name='IP address')
    user_agent = models.TextField(blank=True, verbose_name='User Agent')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Created at')

    class Meta:
        db_table = 'apihh_main_adminlog'
        verbose_name = 'Admin log'
        verbose_name_plural = 'Admin logs'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.admin.username} - {self.action.name} - {self.created_at}"


class Backup(models.Model):
    BACKUP_TYPES = [
        ('full', 'Full backup'),
        ('database', 'Database only'),
        ('media', 'Media only'),
    ]

    name = models.CharField(max_length=255, verbose_name='Backup name')
    backup_file = models.FileField(upload_to='backups/%Y/%m/%d/', verbose_name='Backup file')
    backup_type = models.CharField(max_length=20, choices=BACKUP_TYPES, default='database')
    file_size = models.BigIntegerField(default=0, verbose_name='File size')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Created at')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='Created by')

    class Meta:
        db_table = 'apihh_main_backup'
        verbose_name = 'Backup'
        verbose_name_plural = 'Backups'
        ordering = ['-created_at']

    def delete(self, *args, **kwargs):
        if self.backup_file and os.path.isfile(self.backup_file.path):
            os.remove(self.backup_file.path)
        super().delete(*args, **kwargs)

    def get_file_size_display(self):
        if self.file_size == 0:
            return '0 B'

        size_names = ['B', 'KB', 'MB', 'GB']
        size = float(self.file_size)
        idx = 0
        while size >= 1024 and idx < len(size_names) - 1:
            size /= 1024.0
            idx += 1
        return f"{size:.2f} {size_names[idx]}"

    def __str__(self):
        return self.name
