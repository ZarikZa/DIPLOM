from __future__ import annotations

from unittest.mock import patch

from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse


class DummyResponse:
    def __init__(self, status_code: int, payload=None):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        if self._payload is None:
            raise ValueError("No JSON payload")
        return self._payload


class DeleteCompanyProfileViewTests(TestCase):
    def _set_company_session(self):
        session = self.client.session
        session["api_access"] = "token"
        session["api_refresh"] = "refresh"
        session["api_user"] = {
            "user_type": "company",
            "email": "company@example.com",
        }
        session["ui_theme"] = "dark"
        session.save()

    def test_delete_company_profile_success_clears_session_and_redirects_home(self):
        self._set_company_session()

        with patch("compani.views.api_delete", return_value=DummyResponse(204)):
            response = self.client.post(reverse("delete_company_profile"), follow=True)

        self.assertRedirects(response, reverse("home_page"))
        session = self.client.session
        self.assertNotIn("api_access", session)
        self.assertNotIn("api_refresh", session)
        self.assertNotIn("api_user", session)

        messages = [message.message for message in get_messages(response.wsgi_request)]
        self.assertIn("Компания и связанные данные удалены без возможности восстановления.", messages)

    def test_delete_company_profile_shows_api_error_and_keeps_session(self):
        self._set_company_session()

        with patch(
            "compani.views.api_delete",
            return_value=DummyResponse(403, {"detail": "Удаление аккаунта доступно только соискателю или владельцу компании."}),
        ):
            response = self.client.post(reverse("delete_company_profile"), follow=True)

        self.assertRedirects(response, reverse("company_profile"))
        self.assertIn("api_access", self.client.session)

        messages = [message.message for message in get_messages(response.wsgi_request)]
        self.assertIn("Удаление аккаунта доступно только соискателю или владельцу компании.", messages)


class CompanyProfileEmailChangeFlowTests(TestCase):
    def _set_company_session(self):
        session = self.client.session
        session["api_access"] = "token"
        session["api_refresh"] = "refresh"
        session["api_user"] = {
            "user_type": "company",
            "email": "owner@example.com",
            "phone": "+79990001122",
        }
        session.save()

    def _set_staff_session(self):
        session = self.client.session
        session["api_access"] = "token"
        session["api_refresh"] = "refresh"
        session["api_user"] = {
            "user_type": "staff",
            "employee_role": "hr",
            "email": "employee@example.com",
            "phone": "+79990002233",
        }
        session.save()

    @patch("compani.views.api_post")
    @patch("compani.views.api_patch")
    @patch("compani.views._load_user_profile")
    @patch("compani.views._load_company_me")
    def test_edit_company_profile_requests_email_change_code(
        self,
        mocked_load_company,
        mocked_load_user,
        mocked_api_patch,
        mocked_api_post,
    ):
        self._set_company_session()
        mocked_load_company.return_value = (
            {"name": "WorkMPT", "number": "1234567890", "industry": "IT", "description": "Desc"},
            None,
        )
        mocked_load_user.return_value = (
            {"email": "owner@example.com", "phone": "+79990001122"},
            None,
        )
        mocked_api_patch.side_effect = [
            DummyResponse(200, {"name": "WorkMPT", "number": "1234567890", "industry": "IT", "description": "Updated"}),
            DummyResponse(200, {"email": "owner@example.com", "phone": "+79990001122"}),
        ]
        mocked_api_post.return_value = DummyResponse(200, {"detail": "ok"})

        response = self.client.post(
            reverse("edit_company_profile"),
            data={
                "company_name": "WorkMPT",
                "company_number": "1234567890",
                "industry": "IT",
                "description": "Updated",
                "email": "new-owner@example.com",
                "phone": "+79990001122",
            },
            follow=True,
        )

        self.assertRedirects(response, reverse("company_profile_email_change_verify"))
        self.assertEqual(self.client.session.get("pending_company_profile_email_change"), "new-owner@example.com")
        self.assertEqual(mocked_api_post.call_args.args[1], "user/profile/request-email-change/")

    @patch("compani.views.api_post")
    def test_company_profile_email_verify_updates_session_email(self, mocked_api_post):
        self._set_company_session()
        session = self.client.session
        session["pending_company_profile_email_change"] = "new-owner@example.com"
        session["pending_company_profile_email_change_target"] = "company"
        session.save()
        mocked_api_post.return_value = DummyResponse(200, {"email": "new-owner@example.com"})

        response = self.client.post(
            reverse("company_profile_email_change_verify"),
            data={"code": "123456"},
            follow=False,
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("company_profile"))
        self.assertEqual((self.client.session.get("api_user") or {}).get("email"), "new-owner@example.com")
        self.assertIsNone(self.client.session.get("pending_company_profile_email_change"))

    @patch("compani.views.api_post")
    @patch("compani.views.api_patch")
    @patch("compani.views._load_user_profile")
    def test_edit_employee_profile_requests_email_change_code(
        self,
        mocked_load_user,
        mocked_api_patch,
        mocked_api_post,
    ):
        self._set_staff_session()
        mocked_load_user.return_value = (
            {
                "first_name": "Ivan",
                "last_name": "Petrov",
                "email": "employee@example.com",
                "phone": "+79990002233",
            },
            None,
        )
        mocked_api_patch.return_value = DummyResponse(
            200,
            {
                "first_name": "Ivan",
                "last_name": "Petrov",
                "email": "employee@example.com",
                "phone": "+79990002233",
            },
        )
        mocked_api_post.return_value = DummyResponse(200, {"detail": "ok"})

        response = self.client.post(
            reverse("edit_employee_profile"),
            data={
                "first_name": "Ivan",
                "last_name": "Petrov",
                "email": "new-employee@example.com",
                "phone": "+79990002233",
            },
            follow=True,
        )

        self.assertRedirects(response, reverse("company_profile_email_change_verify"))
        self.assertEqual(self.client.session.get("pending_company_profile_email_change"), "new-employee@example.com")
        self.assertEqual(self.client.session.get("pending_company_profile_email_change_target"), "employee")
