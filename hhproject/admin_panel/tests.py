from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path

from django.contrib.messages import get_messages
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import connection
from django.test import TestCase
from django.urls import reverse

from admin_panel.statistics_service import StatisticsService
from apihh_main.models import (
    ActionType,
    AdminLog,
    Applicant,
    Backup,
    Company,
    Complaint,
    StatusVacancies,
    User,
    Vacancy,
    WorkConditions,
)


class AdminPanelTestMixin:
    def create_user(
        self,
        *,
        email: str,
        username: str,
        user_type: str,
        phone: str,
        password: str = 'StrongPass123!',
        is_superuser: bool = False,
    ) -> User:
        user = User.objects.create_user(
            email=email,
            username=username,
            phone=phone,
            password=password,
            user_type=user_type,
        )
        if is_superuser:
            user.is_superuser = True
            user.is_staff = True
            user.save(update_fields=['is_superuser', 'is_staff'])
        return user

    def create_company_with_vacancy(self) -> Vacancy:
        company_user = self.create_user(
            email='company@example.com',
            username='company@example.com',
            user_type='company',
            phone='79990000001',
        )
        company = Company.objects.create(
            user=company_user,
            name='Test Company',
            number='1234567890',
            industry='IT',
            description='Company description',
            status=Company.STATUS_APPROVED,
            verification_document='company_documents/test.pdf',
        )
        work_conditions = WorkConditions.objects.create(work_conditions_name='Удаленно')
        vacancy_status = StatusVacancies.objects.create(status_vacancies_name='Активная')
        return Vacancy.objects.create(
            company=company,
            work_conditions=work_conditions,
            position='Python developer',
            description='Vacancy description',
            requirements='Vacancy requirements',
            salary_min='100000.00',
            salary_max='200000.00',
            status=vacancy_status,
            city='Москва',
            category='IT',
        )

    def create_applicant(self) -> Applicant:
        applicant_user = self.create_user(
            email='applicant@example.com',
            username='applicant@example.com',
            user_type='applicant',
            phone='79990000002',
        )
        return Applicant.objects.create(
            user=applicant_user,
            first_name='Иван',
            last_name='Иванов',
            birth_date=date(2000, 1, 1),
            resume='Resume',
        )


class ComplaintStatusTests(AdminPanelTestMixin, TestCase):
    def setUp(self):
        self.admin_user = self.create_user(
            email='admin@example.com',
            username='admin@example.com',
            user_type='adminsite',
            phone='79990000003',
        )
        self.client.force_login(self.admin_user)

    def test_update_complaint_status_maps_legacy_resolved_to_reviewed(self):
        vacancy = self.create_company_with_vacancy()
        applicant = self.create_applicant()
        complaint = Complaint.objects.create(
            vacancy=vacancy,
            complainant=applicant.user,
            complaint_type='spam',
            description='Test complaint',
        )

        response = self.client.post(
            reverse('update_complaint_status', args=[complaint.id]),
            data={'status': 'resolved', 'admin_notes': 'Reviewed by admin'},
            follow=True,
        )

        complaint.refresh_from_db()
        self.assertRedirects(response, reverse('complaint_detail', args=[complaint.id]))
        self.assertEqual(complaint.status, Complaint.STATUS_REVIEWED)
        self.assertEqual(complaint.admin_notes, 'Reviewed by admin')
        self.assertIsNotNone(complaint.resolved_at)


class SuperuserProfileGuardTests(AdminPanelTestMixin, TestCase):
    def test_superuser_cannot_open_profile_edit_page(self):
        superuser = self.create_user(
            email='root@example.com',
            username='root@example.com',
            user_type='adminsite',
            phone='79990000004',
            is_superuser=True,
        )
        self.client.force_login(superuser)

        response = self.client.get(reverse('admin_profile_edit'), follow=True)

        self.assertRedirects(response, reverse('admin_profile'))
        self.assertNotContains(response, reverse('admin_profile_edit'))
        messages = [message.message for message in get_messages(response.wsgi_request)]
        self.assertIn('Редактирование профиля недоступно для суперпользователя.', messages)


class BackupManagementTests(AdminPanelTestMixin, TestCase):
    def setUp(self):
        self.admin_user = self.create_user(
            email='backup-admin@example.com',
            username='backup-admin@example.com',
            user_type='adminsite',
            phone='79990000005',
        )
        self.client.force_login(self.admin_user)
        temp_root = Path(__file__).resolve().parent.parent / '_test_tmp'
        temp_root.mkdir(parents=True, exist_ok=True)
        self.temp_dir = temp_root / self._testMethodName
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(self.temp_dir, ignore_errors=True))

    def test_create_backup_api_creates_zip_backup_record(self):
        with self.settings(
            MEDIA_ROOT=str(self.temp_dir),
            FILE_UPLOAD_TEMP_DIR=str(self.temp_dir),
            USE_S3_MEDIA=False,
        ):
            response = self.client.post(
                reverse('admin_create_backup'),
                data={'type': 'database', 'custom_name': 'nightly'},
            )

            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.json()['success'])

            backup = Backup.objects.get()
            self.assertEqual(backup.backup_type, 'database')
            self.assertTrue(backup.name.endswith('.zip'))
            self.assertTrue(backup.backup_file.name.endswith('.zip'))
            self.assertTrue(backup.backup_file.name.startswith('backups/'))
            self.assertGreater(backup.file_size, 0)
            self.assertTrue(default_storage.exists(backup.backup_file.name))
            self.assertTrue(ActionType.objects.filter(code='backup_created').exists())
            self.assertTrue(AdminLog.objects.filter(action__code='backup_created').exists())

    def test_backup_dashboard_contains_system_status_and_media_placeholders(self):
        response = self.client.get(reverse('admin_backup_management'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="totalBackups"', html=False)
        self.assertContains(response, 'id="totalSize"', html=False)
        self.assertContains(response, 'id="databaseSize"', html=False)
        self.assertContains(response, 'id="freeSpace"', html=False)
        self.assertContains(response, 'id="mediaStats"', html=False)

    def test_create_backup_api_recovers_from_postgresql_sequence_drift(self):
        if connection.vendor != 'postgresql':
            self.skipTest('Sequence drift test is relevant only for PostgreSQL.')

        with self.settings(
            MEDIA_ROOT=str(self.temp_dir),
            FILE_UPLOAD_TEMP_DIR=str(self.temp_dir),
            USE_S3_MEDIA=False,
        ):
            existing_backup = Backup(
                name='existing.zip',
                backup_type='database',
                file_size=4,
                created_by=self.admin_user,
            )
            existing_backup.backup_file.save('existing.zip', ContentFile(b'test', name='existing.zip'), save=False)
            existing_backup.save(force_insert=True)

            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT setval(pg_get_serial_sequence(%s, %s), %s, %s)",
                    [Backup._meta.db_table, 'id', 1, False],
                )

            response = self.client.post(
                reverse('admin_create_backup'),
                data={'type': 'database', 'custom_name': 'sequence-fix'},
            )

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertTrue(payload['success'])
            self.assertEqual(Backup.objects.count(), 2)


class StatisticsServiceTests(AdminPanelTestMixin, TestCase):
    def test_empty_platform_statistics_do_not_include_admin_accounts_or_demo_data(self):
        self.create_user(
            email='root@example.com',
            username='root@example.com',
            user_type='adminsite',
            phone='79990000099',
            is_superuser=True,
        )

        main_stats = StatisticsService.get_main_statistics()
        user_distribution = StatisticsService.get_user_type_distribution()
        vacancy_stats = StatisticsService.get_vacancy_statistics()
        complaint_stats = StatisticsService.get_complaint_statistics()

        self.assertEqual(main_stats['total_users'], 0)
        self.assertEqual(main_stats['new_users_week'], 0)
        self.assertEqual(user_distribution['total'], 0)
        self.assertEqual(vacancy_stats['category']['labels'], [])
        self.assertEqual(vacancy_stats['category']['data'], [])
        self.assertEqual(complaint_stats['type_distribution']['labels'], [])
        self.assertEqual(complaint_stats['type_distribution']['data'], [])
