from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse

from home import views as home_views


class DummyResponse:
    def __init__(self, status_code: int, payload=None):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        if self._payload is None:
            raise ValueError("No JSON payload")
        return self._payload


class ApplicantRegistrationVerificationTests(TestCase):
    def _registration_payload(self):
        return {
            "first_name": "Иван",
            "last_name": "Иванов",
            "phone": "+79991234567",
            "email": "new-applicant@example.com",
            "birth_date": "2000-01-01",
            "resume": "Python Django developer",
            "password1": "StrongPass123",
            "password2": "StrongPass123",
            "personal_data_agreement": "on",
        }

    @patch("home.views.send_email_message", return_value=True)
    @patch("home.views.api_post")
    @patch("home.views._generate_registration_code", return_value="123456")
    def test_custom_register_sends_email_code_before_api_registration(
        self,
        mocked_code,
        mocked_api_post,
        mocked_send_email,
    ):
        response = self.client.post(reverse("registration_user"), data=self._registration_payload(), follow=True)

        self.assertRedirects(response, reverse("registration_verify_email"))
        mocked_api_post.assert_not_called()
        mocked_send_email.assert_called_once()
        self.assertEqual(self.client.session.get(home_views.REGISTRATION_ATTEMPTS_SESSION_KEY), 3)
        self.assertEqual(
            self.client.session.get(home_views.REGISTRATION_CODE_HASH_SESSION_KEY),
            home_views._registration_code_hash("new-applicant@example.com", "123456"),
        )

    @patch("home.views.send_email_message", return_value=True)
    @patch("home.views.api_post")
    @patch("home.views._generate_registration_code", return_value="123456")
    def test_registration_verify_email_completes_registration_and_login(
        self,
        mocked_code,
        mocked_api_post,
        mocked_send_email,
    ):
        mocked_api_post.side_effect = [
            DummyResponse(201),
            DummyResponse(
                200,
                {
                    "access": "access-token",
                    "refresh": "refresh-token",
                    "user_id": 12,
                    "email": "new-applicant@example.com",
                    "username": "new-applicant@example.com",
                    "user_type": "applicant",
                    "first_name": "Иван",
                    "last_name": "Иванов",
                },
            ),
        ]

        self.client.post(reverse("registration_user"), data=self._registration_payload())
        response = self.client.post(reverse("registration_verify_email"), data={"code": "123456"}, follow=True)

        self.assertRedirects(response, reverse("applicant_profile"))
        self.assertEqual(mocked_api_post.call_count, 2)
        self.assertIsNone(self.client.session.get(home_views.REGISTRATION_PENDING_SESSION_KEY))
        self.assertEqual(self.client.session.get("api_access"), "access-token")
        self.assertEqual((self.client.session.get("api_user") or {}).get("user_type"), "applicant")

    @patch("home.views.send_email_message", return_value=True)
    @patch("home.views.api_post")
    @patch("home.views._generate_registration_code", return_value="123456")
    def test_registration_verify_email_rejects_wrong_code_without_api_call(
        self,
        mocked_code,
        mocked_api_post,
        mocked_send_email,
    ):
        self.client.post(reverse("registration_user"), data=self._registration_payload())
        response = self.client.post(reverse("registration_verify_email"), data={"code": "000000"})

        self.assertEqual(response.status_code, 200)
        mocked_api_post.assert_not_called()
        self.assertEqual(self.client.session.get(home_views.REGISTRATION_ATTEMPTS_SESSION_KEY), 2)
        self.assertContains(response, "Неверный код подтверждения.", count=1)
        self.assertContains(response, "Неверный код подтверждения.")


class ApplicantProfileEmailChangeFlowTests(TestCase):
    def _set_applicant_session(self):
        session = self.client.session
        session["api_access"] = "token"
        session["api_refresh"] = "refresh"
        session["api_user"] = {
            "user_type": "applicant",
            "email": "old-email@example.com",
            "first_name": "Ivan",
            "last_name": "Ivanov",
        }
        session.save()

    @patch("home.views.api_get")
    @patch("home.views.api_post")
    @patch("home.views.api_patch")
    def test_edit_profile_requests_email_change_code(
        self,
        mocked_api_patch,
        mocked_api_post,
        mocked_api_get,
    ):
        self._set_applicant_session()
        mocked_api_get.return_value = DummyResponse(
            200,
            {
                "first_name": "Ivan",
                "last_name": "Ivanov",
                "email": "old-email@example.com",
                "phone": "+79990001122",
            },
        )
        mocked_api_patch.return_value = DummyResponse(
            200,
            {
                "first_name": "Petr",
                "last_name": "Petrov",
                "email": "old-email@example.com",
                "phone": "+79990001122",
            },
        )
        mocked_api_post.return_value = DummyResponse(200, {"detail": "ok"})

        response = self.client.post(
            reverse("edit_applicant_profile"),
            data={
                "first_name": "Petr",
                "last_name": "Petrov",
                "phone": "+79990001122",
                "birth_date": "1999-01-01",
                "resume": "Updated resume",
                "email": "new-email@example.com",
            },
            follow=True,
        )

        self.assertRedirects(response, reverse("applicant_profile_email_change_verify"))
        self.assertEqual(
            self.client.session.get(home_views.PROFILE_EMAIL_CHANGE_SESSION_KEY),
            "new-email@example.com",
        )
        self.assertEqual(mocked_api_post.call_args.args[1], "user/profile/request-email-change/")
        self.assertNotIn("email", mocked_api_patch.call_args.kwargs.get("json", {}))

    @patch("home.views.api_post")
    def test_verify_email_change_updates_session_email(self, mocked_api_post):
        self._set_applicant_session()
        session = self.client.session
        session[home_views.PROFILE_EMAIL_CHANGE_SESSION_KEY] = "new-email@example.com"
        session.save()
        mocked_api_post.return_value = DummyResponse(200, {"email": "new-email@example.com"})

        response = self.client.post(
            reverse("applicant_profile_email_change_verify"),
            data={"code": "123456"},
            follow=False,
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("applicant_profile"))
        self.assertEqual((self.client.session.get("api_user") or {}).get("email"), "new-email@example.com")
        self.assertIsNone(self.client.session.get(home_views.PROFILE_EMAIL_CHANGE_SESSION_KEY))


class ApplicantRoutesAccessTests(TestCase):
    def _set_admin_session(self):
        session = self.client.session
        session["api_access"] = "token"
        session["api_refresh"] = "refresh"
        session["api_user"] = {
            "user_type": "adminsite",
            "email": "admin@example.com",
        }
        session.save()

    def test_applicant_profile_rejects_admin_access(self):
        self._set_admin_session()

        response = self.client.get(reverse("applicant_profile"), follow=True)

        self.assertRedirects(response, reverse("home_page"))
        messages = [message.message for message in get_messages(response.wsgi_request)]
        self.assertIn("Профиль соискателя доступен только соискателям.", messages)

    def test_applicant_chats_reject_admin_access(self):
        self._set_admin_session()

        response = self.client.get(reverse("applicant_chats"), follow=True)

        self.assertRedirects(response, reverse("home_page"))
        messages = [message.message for message in get_messages(response.wsgi_request)]
        self.assertIn("Чаты соискателя доступны только соискателям.", messages)


class HeaderVisibilityTests(TestCase):
    def test_superuser_does_not_see_applicant_links_even_with_applicant_session(self):
        user_model = get_user_model()
        superuser = user_model.objects.create_user(
            email="superuser@example.com",
            username="superuser@example.com",
            phone="+79990001111",
            password="StrongPass123!",
            user_type="adminsite",
        )
        superuser.is_superuser = True
        superuser.is_staff = True
        superuser.save(update_fields=["is_superuser", "is_staff"])

        self.client.force_login(superuser)
        session = self.client.session
        session["api_user"] = {
            "user_type": "applicant",
            "email": "applicant@example.com",
        }
        session.save()

        with patch("home.views.api_get", return_value=DummyResponse(200, {"count": 0})):
            response = self.client.get(reverse("home_page"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'class="header-link">Профиль</a>', html=False)
        self.assertNotContains(response, 'class="header-link">Видео</a>', html=False)
        self.assertNotContains(response, 'class="header-link">Чаты</a>', html=False)
        self.assertNotContains(response, 'class="mobile-link">Профиль</a>', html=False)
        self.assertNotContains(response, 'class="mobile-link">Видео</a>', html=False)
        self.assertNotContains(response, 'class="mobile-link">Чаты</a>', html=False)


class DeleteApplicantProfileViewTests(TestCase):
    def _set_applicant_session(self):
        session = self.client.session
        session["api_access"] = "token"
        session["api_refresh"] = "refresh"
        session["api_user"] = {
            "user_type": "applicant",
            "email": "applicant@example.com",
        }
        session["ui_theme"] = "dark"
        session.save()

    def test_delete_applicant_profile_success_clears_session_and_redirects_home(self):
        self._set_applicant_session()

        with patch("home.views.api_delete", return_value=DummyResponse(204)):
            response = self.client.post(reverse("delete_applicant_profile"), follow=True)

        self.assertRedirects(response, reverse("home_page"))
        session = self.client.session
        self.assertNotIn("api_access", session)
        self.assertNotIn("api_refresh", session)
        self.assertNotIn("api_user", session)

        messages = [message.message for message in get_messages(response.wsgi_request)]
        self.assertIn("Аккаунт удалён без возможности восстановления.", messages)

    def test_delete_applicant_profile_rejects_non_applicant(self):
        session = self.client.session
        session["api_access"] = "token"
        session["api_user"] = {
            "user_type": "company",
            "email": "company@example.com",
        }
        session.save()

        with patch("home.views.api_delete") as mocked_delete:
            response = self.client.post(reverse("delete_applicant_profile"), follow=True)

        self.assertRedirects(response, reverse("home_comp"))
        mocked_delete.assert_not_called()

        messages = [message.message for message in get_messages(response.wsgi_request)]
        self.assertIn("Удаление аккаунта доступно только соискателям.", messages)

    def test_delete_applicant_profile_shows_api_error_and_keeps_session(self):
        self._set_applicant_session()

        with patch(
            "home.views.api_delete",
            return_value=DummyResponse(403, {"detail": "Удаление аккаунта через мобильное приложение доступно только соискателям."}),
        ):
            response = self.client.post(reverse("delete_applicant_profile"), follow=True)

        self.assertRedirects(response, reverse("applicant_profile"))
        self.assertIn("api_access", self.client.session)

        messages = [message.message for message in get_messages(response.wsgi_request)]
        self.assertIn("Удаление аккаунта через мобильное приложение доступно только соискателям.", messages)
