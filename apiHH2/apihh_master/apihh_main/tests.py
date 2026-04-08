from datetime import date
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from rest_framework import status
from rest_framework.test import APITestCase

from .models import (
    Applicant,
    ApplicantInterest,
    Company,
    Employee,
    Favorites,
    Response,
    StatusResponse,
    StatusVacancies,
    User,
    Vacancy,
    VacancyCategorySuggestion,
    VacancyVideo,
    VacancyVideoLike,
    VacancyVideoView,
    WorkConditions,
)


class ConsoleResultMixin:
    def run(self, result=None):
        if result is None:
            result = self.defaultTestResult()

        before = self._result_counters(result)
        super().run(result)
        after = self._result_counters(result)

        has_failure = (
            after["errors"] > before["errors"]
            or after["failures"] > before["failures"]
            or after["expected_failures"] > before["expected_failures"]
            or after["unexpected_successes"] > before["unexpected_successes"]
        )
        has_skip = after["skipped"] > before["skipped"]

        if has_failure:
            print(f"[FAIL] {self.id()}")
        elif has_skip:
            print(f"[SKIP] {self.id()}")
        else:
            print(f"[PASS] {self.id()}")

        return result

    def _result_counters(self, result):
        return {
            "errors": len(getattr(result, "errors", [])),
            "failures": len(getattr(result, "failures", [])),
            "skipped": len(getattr(result, "skipped", [])),
            "expected_failures": len(getattr(result, "expectedFailures", [])),
            "unexpected_successes": len(getattr(result, "unexpectedSuccesses", [])),
        }


class ApiTestDataMixin:
    def create_user(
        self,
        *,
        email,
        username,
        user_type,
        phone="79990000000",
        password="StrongPass123!",
    ):
        return User.objects.create_user(
            email=email,
            username=username,
            phone=phone,
            password=password,
            user_type=user_type,
        )

    def create_company_user_and_company(
        self,
        *,
        email,
        username,
        company_name="Test Company",
    ):
        user = self.create_user(
            email=email,
            username=username,
            user_type="company",
        )
        company = Company.objects.create(
            user=user,
            name=company_name,
            number="1234567890",
            industry="IT",
            description="Test description",
            verification_document="company_documents/test.pdf",
        )
        return user, company

    def create_applicant_user_and_profile(
        self,
        *,
        email,
        username,
    ):
        user = self.create_user(
            email=email,
            username=username,
            user_type="applicant",
        )
        applicant = Applicant.objects.create(
            user=user,
            first_name="Ivan",
            last_name="Ivanov",
            birth_date=date(1995, 1, 1),
            resume="Resume",
        )
        return user, applicant

    def create_vacancy(self, *, company, position, is_archived=False, category="IT"):
        work_conditions = WorkConditions.objects.create(work_conditions_name="Remote")
        vacancy_status = StatusVacancies.objects.create(status_vacancies_name="Open")
        return Vacancy.objects.create(
            company=company,
            work_conditions=work_conditions,
            position=position,
            description="Vacancy description",
            requirements="Vacancy requirements",
            salary_min="100000.00",
            salary_max="200000.00",
            status=vacancy_status,
            city="Moscow",
            category=category,
            is_archived=is_archived,
        )

    def extract_items(self, response):
        payload = response.data
        if isinstance(payload, dict) and "results" in payload:
            return payload["results"]
        return payload

    def make_pdf_file(self, name="verification.pdf", content=b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF"):
        return SimpleUploadedFile(name, content, content_type="application/pdf")


class ApiTestCase(ConsoleResultMixin, ApiTestDataMixin, APITestCase):
    pass


class PublicCompanyApiTests(ApiTestCase):
    def test_companies_list_public_for_anonymous(self):
        response = self.client.get("/api/companies/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_companies_create_requires_authentication(self):
        response = self.client.post("/api/companies/", data={}, format="json")
        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

    def test_company_me_requires_authentication(self):
        response = self.client.get("/api/company/me/")
        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )


class CompanyCabinetApiTests(ApiTestCase):
    def setUp(self):
        self.owner_user, self.company = self.create_company_user_and_company(
            email="owner@example.com",
            username="owner",
        )
        self.client.force_authenticate(self.owner_user)

    def test_company_me_returns_company_for_owner(self):
        response = self.client.get("/api/company/me/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.company.id)

    def test_company_me_patch_updates_company_name(self):
        response = self.client.patch(
            "/api/company/me/",
            data={"name": "Updated Company Name"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.company.refresh_from_db()
        self.assertEqual(self.company.name, "Updated Company Name")

    def test_company_vacancies_default_excludes_archived(self):
        visible = self.create_vacancy(
            company=self.company,
            position="Visible vacancy",
            is_archived=False,
        )
        archived = self.create_vacancy(
            company=self.company,
            position="Archived vacancy",
            is_archived=True,
        )

        response = self.client.get("/api/company/vacancies/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        ids = {item["id"] for item in self.extract_items(response)}
        self.assertIn(visible.id, ids)
        self.assertNotIn(archived.id, ids)

    def test_company_vacancies_archived_query_returns_all(self):
        visible = self.create_vacancy(
            company=self.company,
            position="Visible vacancy",
            is_archived=False,
        )
        archived = self.create_vacancy(
            company=self.company,
            position="Archived vacancy",
            is_archived=True,
        )

        response = self.client.get("/api/company/vacancies/?archived=1")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        ids = {item["id"] for item in self.extract_items(response)}
        self.assertIn(visible.id, ids)
        self.assertIn(archived.id, ids)

    def test_company_vacancy_create_without_company_field(self):
        work_conditions = WorkConditions.objects.create(work_conditions_name="Remote")
        vacancy_status = StatusVacancies.objects.create(status_vacancies_name="Open")
        payload = {
            "work_conditions": work_conditions.id,
            "position": "Backend Developer",
            "description": "Описание вакансии",
            "requirements": "Требования вакансии",
            "salary_min": "120000.00",
            "salary_max": "180000.00",
            "status": vacancy_status.id,
            "city": "Москва",
            "category": "IT",
            "experience": "1-3 года",
            "work_conditions_details": "Удаленная работа",
        }

        response = self.client.post("/api/company/vacancies/", data=payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["position"], payload["position"])
        self.assertEqual(response.data["company"], self.company.id)

    def test_company_vacancy_create_rejects_invalid_salary_range(self):
        work_conditions = WorkConditions.objects.create(work_conditions_name="Office")
        vacancy_status = StatusVacancies.objects.create(status_vacancies_name="Open")
        payload = {
            "work_conditions": work_conditions.id,
            "position": "Python Developer",
            "description": "Подробное описание вакансии с обязанностями",
            "requirements": "Опыт работы с Python и Django не менее года",
            "salary_min": "250000.00",
            "salary_max": "150000.00",
            "status": vacancy_status.id,
            "city": "Москва",
            "category": "IT",
            "experience": "1-3 года",
            "work_conditions_details": "Удаленный формат работы",
        }

        response = self.client.post("/api/company/vacancies/", data=payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("salary_min", response.data)
        self.assertIn("salary_max", response.data)

    def test_company_vacancy_create_rejects_profanity(self):
        work_conditions = WorkConditions.objects.create(work_conditions_name="Hybrid")
        vacancy_status = StatusVacancies.objects.create(status_vacancies_name="Open")
        payload = {
            "work_conditions": work_conditions.id,
            "position": "хуй разработчик",
            "description": "Подробное описание вакансии с обязанностями",
            "requirements": "Опыт работы с Python и Django не менее года",
            "salary_min": "120000.00",
            "salary_max": "180000.00",
            "status": vacancy_status.id,
            "city": "Москва",
            "category": "IT",
            "experience": "1-3 года",
            "work_conditions_details": "Удаленный формат работы",
        }

        response = self.client.post("/api/company/vacancies/", data=payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("position", response.data)


class VacancyCategorySuggestionApiTests(ApiTestCase):
    def setUp(self):
        self.owner_user, self.company = self.create_company_user_and_company(
            email="category_owner@example.com",
            username="category_owner",
            company_name="Category Company",
        )
        self.admin_user = self.create_user(
            email="category_admin@example.com",
            username="category_admin",
            user_type="adminsite",
        )
        self.client.force_authenticate(self.owner_user)

    def _vacancy_payload(self, category: str):
        work_conditions = WorkConditions.objects.create(work_conditions_name="Remote")
        vacancy_status = StatusVacancies.objects.create(status_vacancies_name="Open")
        return {
            "work_conditions": work_conditions.id,
            "position": "Data Analyst",
            "description": "Подробное описание вакансии для аналитика данных",
            "requirements": "Опыт анализа данных и работы с BI инструментами",
            "salary_min": "120000.00",
            "salary_max": "180000.00",
            "status": vacancy_status.id,
            "city": "Москва",
            "category": category,
            "experience": "1-3 года",
            "work_conditions_details": "Удаленная работа",
        }

    def test_company_can_submit_unique_category_suggestion(self):
        response = self.client.post(
            "/api/company/vacancy-category-suggestions/",
            data={"name": "Data Science"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], VacancyCategorySuggestion.STATUS_PENDING)

        duplicate_response = self.client.post(
            "/api/company/vacancy-category-suggestions/",
            data={"name": "data   science"},
            format="json",
        )
        self.assertEqual(duplicate_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("name", duplicate_response.data)

    def test_category_suggestion_rejects_profanity(self):
        response = self.client.post(
            "/api/company/vacancy-category-suggestions/",
            data={"name": "хуйня"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("name", response.data)

    def test_admin_approval_adds_category_to_available_and_allows_vacancy_create(self):
        create_response = self.client.post(
            "/api/company/vacancy-category-suggestions/",
            data={"name": "Финансы"},
            format="json",
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        suggestion_id = create_response.data["id"]

        self.client.force_authenticate(self.admin_user)
        approve_response = self.client.patch(
            f"/api/admin/vacancy-category-suggestions/{suggestion_id}/",
            data={"status": VacancyCategorySuggestion.STATUS_APPROVED, "admin_notes": "Подходит"},
            format="json",
        )
        self.assertEqual(approve_response.status_code, status.HTTP_200_OK)

        categories_response = self.client.get("/api/vacancy-categories/")
        self.assertEqual(categories_response.status_code, status.HTTP_200_OK)
        category_names = {item["name"] for item in self.extract_items(categories_response)}
        self.assertIn("Финансы", category_names)

        self.client.force_authenticate(self.owner_user)
        vacancy_response = self.client.post(
            "/api/company/vacancies/",
            data=self._vacancy_payload("Финансы"),
            format="json",
        )
        self.assertEqual(vacancy_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(vacancy_response.data["category"], "Финансы")


class FavoritesToggleApiTests(ApiTestCase):
    def setUp(self):
        self.applicant_user, self.applicant = self.create_applicant_user_and_profile(
            email="applicant@example.com",
            username="applicant",
        )
        self.company_user, self.company = self.create_company_user_and_company(
            email="company@example.com",
            username="company",
        )
        self.vacancy = self.create_vacancy(
            company=self.company,
            position="Python Developer",
        )

    def test_favorites_toggle_for_non_applicant_forbidden(self):
        self.client.force_authenticate(self.company_user)

        response = self.client.post(
            "/api/favorites/toggle/",
            data={"vacancy": self.vacancy.id},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(
            Favorites.objects.filter(
                applicant=self.applicant,
                vacancy=self.vacancy,
            ).exists()
        )

    def test_favorites_toggle_for_applicant_adds_favorite(self):
        self.client.force_authenticate(self.applicant_user)

        response = self.client.post(
            "/api/favorites/toggle/",
            data={"vacancy": self.vacancy.id},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["is_favorite"])
        self.assertTrue(
            Favorites.objects.filter(
                applicant=self.applicant,
                vacancy=self.vacancy,
            ).exists()
        )

    def test_favorites_toggle_for_applicant_removes_existing_favorite(self):
        Favorites.objects.create(applicant=self.applicant, vacancy=self.vacancy)
        self.client.force_authenticate(self.applicant_user)

        response = self.client.post(
            "/api/favorites/toggle/",
            data={"vacancy": self.vacancy.id},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["is_favorite"])
        self.assertFalse(
            Favorites.objects.filter(
                applicant=self.applicant,
                vacancy=self.vacancy,
            ).exists()
        )


class ApplicantRegistrationApiTests(ApiTestCase):
    def test_register_applicant_saves_names_in_user_and_applicant(self):
        payload = {
            "email": "new_applicant@example.com",
            "username": "new_applicant@example.com",
            "phone": "+79990001122",
            "password": "StrongPass123!",
            "password2": "StrongPass123!",
            "first_name": "Ivan",
            "last_name": "Ivanov",
            "birth_date": "2000-05-20",
            "resume": "Junior backend developer",
        }

        response = self.client.post("/api/user/register_applicant/", data=payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email=payload["email"])
        applicant = Applicant.objects.get(user=user)

        self.assertEqual(user.first_name, payload["first_name"])
        self.assertEqual(user.last_name, payload["last_name"])
        self.assertEqual(applicant.first_name, payload["first_name"])
        self.assertEqual(applicant.last_name, payload["last_name"])

    def test_register_applicant_rejects_future_birth_date(self):
        payload = {
            "email": "future_birth@example.com",
            "username": "future_birth@example.com",
            "phone": "+79990001122",
            "password": "StrongPass123!",
            "password2": "StrongPass123!",
            "first_name": "Ivan",
            "last_name": "Ivanov",
            "birth_date": "2999-05-20",
            "resume": "Junior backend developer",
        }

        response = self.client.post("/api/user/register_applicant/", data=payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("birth_date", response.data)

    def test_register_applicant_rejects_profanity_in_resume(self):
        payload = {
            "email": "bad_resume@example.com",
            "username": "bad_resume@example.com",
            "phone": "+79990001122",
            "password": "StrongPass123!",
            "password2": "StrongPass123!",
            "first_name": "Ivan",
            "last_name": "Ivanov",
            "birth_date": "2000-05-20",
            "resume": "blya backend developer",
        }

        response = self.client.post("/api/user/register_applicant/", data=payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("resume", response.data)


class CompanyRegistrationApiTests(ApiTestCase):
    def _build_payload(self, *, email="company@example.com", phone="+79990001122"):
        return {
            "email": email,
            "username": email,
            "phone": phone,
            "password": "StrongPass123!",
            "password2": "StrongPass123!",
            "name": "New Company Name",
            "number": "1234567890",
            "industry": "IT",
            "description": "Detailed company description",
            "verification_document": self.make_pdf_file(),
        }

    def test_register_company_creates_pending_company(self):
        response = self.client.post(
            "/api/user/register_company/",
            data=self._build_payload(),
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email="company@example.com")
        company = Company.objects.get(user=user)
        self.assertEqual(user.user_type, "company")
        self.assertEqual(company.status, Company.STATUS_PENDING)

    def test_register_company_resubmits_rejected_company_with_same_email(self):
        user, company = self.create_company_user_and_company(
            email="rejected_company@example.com",
            username="rejected_company@example.com",
            company_name="Old Company Name",
        )
        company.status = Company.STATUS_REJECTED
        company.save(update_fields=["status"])

        payload = self._build_payload(email="rejected_company@example.com", phone="+79995554433")
        payload["name"] = "Resubmitted Company Name"
        payload["description"] = "Updated company description after rejection"

        response = self.client.post(
            "/api/user/register_company/",
            data=payload,
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(User.objects.filter(email="rejected_company@example.com").count(), 1)
        self.assertEqual(Company.objects.filter(user=user).count(), 1)

        user.refresh_from_db()
        company.refresh_from_db()
        self.assertEqual(user.phone, "+79995554433")
        self.assertTrue(user.check_password("StrongPass123!"))
        self.assertEqual(company.name, "Resubmitted Company Name")
        self.assertEqual(company.description, "Updated company description after rejection")
        self.assertEqual(company.status, Company.STATUS_PENDING)

    def test_register_company_denies_resubmission_for_pending_company(self):
        self.create_company_user_and_company(
            email="pending_company@example.com",
            username="pending_company@example.com",
        )

        response = self.client.post(
            "/api/user/register_company/",
            data=self._build_payload(email="pending_company@example.com"),
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_register_company_rejects_profanity(self):
        payload = self._build_payload(email="bad_company@example.com")
        payload["description"] = "Наша bLYA компания"

        response = self.client.post(
            "/api/user/register_company/",
            data=payload,
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("description", response.data)

    def test_resubmit_company_accepts_only_rejected_company(self):
        user, company = self.create_company_user_and_company(
            email="resubmit_rejected@example.com",
            username="resubmit_rejected@example.com",
            company_name="Rejected Company",
        )
        company.status = Company.STATUS_REJECTED
        company.save(update_fields=["status"])

        payload = self._build_payload(email="resubmit_rejected@example.com", phone="+79997776655")
        payload["name"] = "Resubmitted Via Dedicated Endpoint"

        response = self.client.post(
            "/api/user/resubmit_company/",
            data=payload,
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        company.refresh_from_db()
        self.assertEqual(user.phone, "+79997776655")
        self.assertEqual(company.name, "Resubmitted Via Dedicated Endpoint")
        self.assertEqual(company.status, Company.STATUS_PENDING)

    def test_resubmit_company_rejects_non_rejected_status(self):
        self.create_company_user_and_company(
            email="resubmit_pending@example.com",
            username="resubmit_pending@example.com",
            company_name="Pending Company",
        )

        response = self.client.post(
            "/api/user/resubmit_company/",
            data=self._build_payload(email="resubmit_pending@example.com"),
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)


class ApplicantProfileApiTests(ApiTestCase):
    def setUp(self):
        self.applicant_user, self.applicant = self.create_applicant_user_and_profile(
            email="profile_applicant@example.com",
            username="profile_applicant",
        )
        self.client.force_authenticate(self.applicant_user)

    def test_profile_patch_updates_applicant_fields(self):
        response = self.client.patch(
            "/api/user/profile/",
            data={
                "first_name": "Petr",
                "last_name": "Petrov",
                "phone": "+79991112233",
                "birth_date": "1998-05-20",
                "resume": "Updated resume text",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.applicant_user.refresh_from_db()
        self.applicant.refresh_from_db()

        self.assertEqual(self.applicant_user.first_name, "Petr")
        self.assertEqual(self.applicant_user.last_name, "Petrov")
        self.assertEqual(self.applicant_user.phone, "+79991112233")
        self.assertEqual(self.applicant.first_name, "Petr")
        self.assertEqual(self.applicant.last_name, "Petrov")
        self.assertEqual(self.applicant.birth_date.isoformat(), "1998-05-20")
        self.assertEqual(self.applicant.resume, "Updated resume text")
        self.assertEqual(response.data["birth_date"], "1998-05-20")
        self.assertEqual(response.data["resume"], "Updated resume text")

    def test_profile_get_falls_back_to_applicant_names_when_user_names_empty(self):
        self.applicant_user.first_name = ""
        self.applicant_user.last_name = ""
        self.applicant_user.save(update_fields=["first_name", "last_name"])

        response = self.client.get("/api/user/profile/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["first_name"], self.applicant.first_name)
        self.assertEqual(response.data["last_name"], self.applicant.last_name)

    def test_profile_patch_uploads_applicant_avatar(self):
        image_buffer = BytesIO()
        Image.new("RGB", (2, 2), color=(32, 64, 192)).save(image_buffer, format="PNG")
        avatar = SimpleUploadedFile("avatar.png", image_buffer.getvalue(), content_type="image/png")

        response = self.client.patch(
            "/api/user/profile/",
            data={"avatar": avatar},
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.applicant.refresh_from_db()
        self.assertTrue(bool(self.applicant.avatar))
        self.assertIn("applicant_avatars/", self.applicant.avatar.name)
        self.assertTrue(response.data.get("avatar"))


class ContentManagerProfileApiTests(ApiTestCase):
    def setUp(self):
        self.owner_user, self.company = self.create_company_user_and_company(
            email="owner_cm@example.com",
            username="owner_cm",
            company_name="CM Test Company",
        )

        self.cm_user = self.create_user(
            email="cm@example.com",
            username="cm_user",
            user_type="staff",
            password="OldStrongPass123!",
        )
        self.employee = Employee.objects.create(
            user=self.cm_user,
            company=self.company,
            role="content_manager",
        )

        self.vacancy_1 = self.create_vacancy(
            company=self.company,
            position="CM Vacancy 1",
        )
        self.vacancy_2 = self.create_vacancy(
            company=self.company,
            position="CM Vacancy 2",
        )

        self.status_response = StatusResponse.objects.create(status_response_name="Отправлен")
        self.applicant_user, self.applicant = self.create_applicant_user_and_profile(
            email="cm_applicant@example.com",
            username="cm_applicant",
        )
        Response.objects.create(
            applicants=self.applicant,
            vacancy=self.vacancy_1,
            status=self.status_response,
        )
        Response.objects.create(
            applicants=self.applicant,
            vacancy=self.vacancy_2,
            status=self.status_response,
        )

        sample_video = SimpleUploadedFile("sample.mp4", b"fake-video-content", content_type="video/mp4")
        self.video = VacancyVideo.objects.create(
            vacancy=self.vacancy_1,
            uploaded_by=self.employee,
            company=self.company,
            video=sample_video,
            description="Demo video",
        )
        VacancyVideoView.objects.create(applicant=self.applicant, video=self.video)
        VacancyVideoLike.objects.create(applicant=self.applicant, video=self.video)

    def test_user_profile_contains_company_fields_for_content_manager(self):
        self.client.force_authenticate(self.cm_user)
        response = self.client.get("/api/user/profile/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["employee_role"], "content_manager")
        self.assertEqual(response.data["company_name"], self.company.name)
        self.assertEqual(response.data["company_industry"], self.company.industry)

    def test_change_password_updates_credentials(self):
        self.client.force_authenticate(self.cm_user)
        response = self.client.post(
            "/api/user/change-password/",
            data={
                "old_password": "OldStrongPass123!",
                "new_password": "NewStrongPass123!",
                "new_password_confirm": "NewStrongPass123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.cm_user.refresh_from_db()
        self.assertTrue(self.cm_user.check_password("NewStrongPass123!"))

    def test_change_password_rejects_wrong_old_password(self):
        self.client.force_authenticate(self.cm_user)
        response = self.client.post(
            "/api/user/change-password/",
            data={
                "old_password": "WrongOldPass123!",
                "new_password": "NewStrongPass123!",
                "new_password_confirm": "NewStrongPass123!",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_content_manager_stats_returns_expected_payload(self):
        self.client.force_authenticate(self.cm_user)
        response = self.client.get("/api/content-manager/profile/stats/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["manager"]["role"], "content_manager")
        self.assertEqual(response.data["company"]["name"], self.company.name)
        self.assertEqual(response.data["stats"]["videos_count"], 1)
        self.assertEqual(response.data["stats"]["vacancies_count"], 2)
        self.assertEqual(response.data["stats"]["responses_count"], 2)
        self.assertIn("labels", response.data["chart"])
        self.assertIn("values", response.data["chart"])

    def test_content_manager_stats_pdf_returns_pdf_file(self):
        self.client.force_authenticate(self.cm_user)
        response = self.client.get("/api/content-manager/profile/stats/pdf/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("attachment;", response["Content-Disposition"])

    def test_content_manager_stats_for_non_cm_forbidden(self):
        self.client.force_authenticate(self.applicant_user)
        response = self.client.get("/api/content-manager/profile/stats/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class FeedVideoApiTests(ApiTestCase):
    def setUp(self):
        self.owner_user, self.company = self.create_company_user_and_company(
            email="feed_owner@example.com",
            username="feed_owner",
            company_name="Feed Test Company",
        )
        self.cm_user = self.create_user(
            email="feed_cm@example.com",
            username="feed_cm",
            user_type="staff",
        )
        self.employee = Employee.objects.create(
            user=self.cm_user,
            company=self.company,
            role="content_manager",
        )
        self.vacancy = self.create_vacancy(company=self.company, position="Feed vacancy")

        self.applicant_user, self.applicant = self.create_applicant_user_and_profile(
            email="feed_applicant@example.com",
            username="feed_applicant",
        )
        sent_status = StatusResponse.objects.create(status_response_name="Отправлен")
        Response.objects.create(
            applicants=self.applicant,
            vacancy=self.vacancy,
            status=sent_status,
        )

        sample_video = SimpleUploadedFile("feed.mp4", b"feed-video-content", content_type="video/mp4")
        self.video = VacancyVideo.objects.create(
            vacancy=self.vacancy,
            uploaded_by=self.employee,
            company=self.company,
            video=sample_video,
            description="Feed video",
            is_active=True,
        )

    def test_recommended_feed_returns_has_applied_inside_vacancy(self):
        self.client.force_authenticate(self.applicant_user)
        response = self.client.get("/api/feed/videos/recommended/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        items = self.extract_items(response)
        self.assertTrue(items)
        self.assertIn("vacancy", items[0])
        self.assertIn("has_applied", items[0]["vacancy"])
        self.assertTrue(items[0]["vacancy"]["has_applied"])


class RecommendationApiTests(ApiTestCase):
    def setUp(self):
        self.applicant_user, self.applicant = self.create_applicant_user_and_profile(
            email="recommend_applicant@example.com",
            username="recommend_applicant",
        )
        self.company_user, self.company = self.create_company_user_and_company(
            email="recommend_company@example.com",
            username="recommend_company",
            company_name="Recommendation Company",
        )
        self.cm_user = self.create_user(
            email="recommend_cm@example.com",
            username="recommend_cm",
            user_type="staff",
        )
        self.employee = Employee.objects.create(
            user=self.cm_user,
            company=self.company,
            role="content_manager",
        )

        self.it_vacancy = self.create_vacancy(
            company=self.company,
            position="Python Engineer",
            category="IT",
        )
        self.hr_vacancy = self.create_vacancy(
            company=self.company,
            position="HR Specialist",
            category="HR",
        )

        self.it_video = VacancyVideo.objects.create(
            vacancy=self.it_vacancy,
            uploaded_by=self.employee,
            company=self.company,
            video=SimpleUploadedFile("it.mp4", b"it-video-content", content_type="video/mp4"),
            description="IT video",
            is_active=True,
        )
        self.hr_video = VacancyVideo.objects.create(
            vacancy=self.hr_vacancy,
            uploaded_by=self.employee,
            company=self.company,
            video=SimpleUploadedFile("hr.mp4", b"hr-video-content", content_type="video/mp4"),
            description="HR video",
            is_active=True,
        )

        self.client.force_authenticate(self.applicant_user)

    def test_me_interests_put_and_get(self):
        update_response = self.client.put(
            "/api/applicants/me/interests/",
            data={"categories": ["IT", "HR"]},
            format="json",
        )
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(set(update_response.data["categories"]), {"IT", "HR"})

        get_response = self.client.get("/api/applicants/me/interests/")
        self.assertEqual(get_response.status_code, status.HTTP_200_OK)
        self.assertEqual(set(get_response.data["categories"]), {"IT", "HR"})
        self.assertIn("available_categories", get_response.data)

    def test_recommended_vacancies_filtered_by_interests(self):
        ApplicantInterest.objects.create(applicant=self.applicant, category="IT")

        response = self.client.get("/api/vacancies/?recommended=1")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        items = self.extract_items(response)
        ids = {item["id"] for item in items}
        self.assertIn(self.it_vacancy.id, ids)
        self.assertNotIn(self.hr_vacancy.id, ids)

    def test_search_ignores_recommendation_filter(self):
        ApplicantInterest.objects.create(applicant=self.applicant, category="IT")

        response = self.client.get("/api/vacancies/?recommended=1&search=HR%20Specialist")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        items = self.extract_items(response)
        ids = {item["id"] for item in items}
        self.assertIn(self.hr_vacancy.id, ids)

    def test_recommended_videos_filtered_by_interests(self):
        ApplicantInterest.objects.create(applicant=self.applicant, category="HR")

        response = self.client.get("/api/feed/videos/recommended/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        items = self.extract_items(response)
        ids = {item["id"] for item in items}
        self.assertIn(self.hr_video.id, ids)
        self.assertNotIn(self.it_video.id, ids)

    def test_vacancies_filter_by_employment(self):
        filter_status = StatusVacancies.objects.create(status_vacancies_name="Filter Open")
        full_time = WorkConditions.objects.create(work_conditions_name="Полная занятость")
        part_time = WorkConditions.objects.create(work_conditions_name="Частичная занятость")

        full_vacancy = Vacancy.objects.create(
            company=self.company,
            work_conditions=full_time,
            position="Full Time Vacancy",
            description="Vacancy description",
            requirements="Vacancy requirements",
            salary_min="100000.00",
            salary_max="200000.00",
            status=filter_status,
            city="Moscow",
            category="IT",
        )
        part_vacancy = Vacancy.objects.create(
            company=self.company,
            work_conditions=part_time,
            position="Part Time Vacancy",
            description="Vacancy description",
            requirements="Vacancy requirements",
            salary_min="100000.00",
            salary_max="200000.00",
            status=filter_status,
            city="Moscow",
            category="IT",
        )

        response_by_name = self.client.get("/api/vacancies/", data={"employment": "Полная занятость"})
        self.assertEqual(response_by_name.status_code, status.HTTP_200_OK)
        ids_by_name = {item["id"] for item in self.extract_items(response_by_name)}
        self.assertIn(full_vacancy.id, ids_by_name)
        self.assertNotIn(part_vacancy.id, ids_by_name)

        response_by_id = self.client.get("/api/vacancies/", data={"employment": str(part_time.id)})
        self.assertEqual(response_by_id.status_code, status.HTTP_200_OK)
        ids_by_id = {item["id"] for item in self.extract_items(response_by_id)}
        self.assertIn(part_vacancy.id, ids_by_id)
        self.assertNotIn(full_vacancy.id, ids_by_id)
