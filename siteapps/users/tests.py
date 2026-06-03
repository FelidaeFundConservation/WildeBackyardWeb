"""Tests for users views, auth backend, and BackendAPIClient."""

from unittest.mock import MagicMock, patch

import requests as requests_lib
from django.contrib.messages import get_messages
from django.test import Client, TestCase
from django.urls import reverse

from siteapps.users.models import User


def make_user(email="user@example.com", password="pass1234!", name="Test User", **kwargs):
    return User.objects.create_user(email=email, password=password, name=name, **kwargs)


class LoginViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse("users:login")
        self.user = make_user("login@example.com")

    def test_get_renders_form(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_authenticated_user_redirected(self):
        self.client.login(email="login@example.com", password="pass1234!")
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse("home:home"), fetch_redirect_response=False)

    def test_missing_credentials_shows_error(self):
        response = self.client.post(self.url, {"email": "", "password": ""})
        self.assertEqual(response.status_code, 200)
        msgs = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(any("provide" in m.lower() or "email" in m.lower() for m in msgs))

    @patch("siteapps.users.views.authenticate")
    def test_invalid_credentials_shows_error(self, mock_auth):
        mock_auth.return_value = None
        response = self.client.post(self.url, {"email": "bad@example.com", "password": "wrongpass"})
        self.assertEqual(response.status_code, 200)
        msgs = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(any("invalid" in m.lower() or "password" in m.lower() for m in msgs))

    @patch("siteapps.users.views.authenticate")
    def test_successful_login_redirects(self, mock_auth):
        mock_auth.return_value = self.user
        with patch("siteapps.users.views.login"):
            response = self.client.post(self.url, {"email": "login@example.com", "password": "pass1234!"})
        self.assertRedirects(response, reverse("home:home"), fetch_redirect_response=False)


class RegisterViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse("users:register")

    def test_get_renders_form(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_authenticated_redirected(self):
        make_user("redir@example.com")
        self.client.login(email="redir@example.com", password="pass1234!")
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse("home:home"), fetch_redirect_response=False)

    def test_missing_email_shows_error(self):
        response = self.client.post(self.url, {"email": "", "password": "pass12345", "password_confirm": "pass12345"})
        msgs = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(any("email" in m.lower() or "required" in m.lower() for m in msgs))

    def test_password_mismatch_shows_error(self):
        response = self.client.post(
            self.url,
            {"email": "new@example.com", "password": "pass12345", "password_confirm": "different"},
        )
        msgs = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(any("match" in m.lower() for m in msgs))

    def test_short_password_shows_error(self):
        response = self.client.post(
            self.url,
            {"email": "new@example.com", "password": "short", "password_confirm": "short"},
        )
        msgs = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(any("8 character" in m.lower() or "short" in m.lower() or "least" in m.lower() for m in msgs))

    @patch("siteapps.users.views.BackendAPIClient")
    def test_successful_registration_redirects_to_login_without_auto_login(self, mock_client_class):
        mock_api = MagicMock()
        mock_api.register_user.return_value = (True, {"email": "fresh@example.com"})
        mock_client_class.return_value = mock_api

        response = self.client.post(
            self.url,
            {
                "email": "fresh@example.com",
                "password": "pass12345",
                "password_confirm": "pass12345",
                "name": "Fresh",
            },
        )

        self.assertRedirects(response, reverse("users:login"), fetch_redirect_response=False)
        self.assertNotIn("_auth_user_id", self.client.session)
        msgs = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(any("verify your account" in m.lower() or "verify your email" in m.lower() for m in msgs))

    @patch("siteapps.users.views.BackendAPIClient")
    def test_registration_api_failure_shows_error(self, mock_client_class):
        mock_api = MagicMock()
        mock_api.register_user.return_value = (False, "Email already exists.")
        mock_client_class.return_value = mock_api

        response = self.client.post(
            self.url,
            {"email": "dup@example.com", "password": "pass12345", "password_confirm": "pass12345"},
        )
        self.assertEqual(response.status_code, 200)
        msgs = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(any("email already" in m.lower() or "exists" in m.lower() for m in msgs))


class LogoutViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse("users:logout")
        self.user = make_user("logout@example.com")

    def test_logout_clears_session_token(self):
        self.client.login(email="logout@example.com", password="pass1234!")
        session = self.client.session
        session["backend_api_token"] = "sometoken"
        session.save()

        with patch("siteapps.users.views.BackendAPIClient") as mock_cls:
            mock_api = MagicMock()
            mock_cls.return_value = mock_api
            response = self.client.post(self.url)

        self.assertRedirects(response, reverse("home:home"), fetch_redirect_response=False)
        self.assertNotIn("backend_api_token", self.client.session)

    def test_logout_without_token(self):
        self.client.login(email="logout@example.com", password="pass1234!")
        response = self.client.post(self.url)
        self.assertRedirects(response, reverse("home:home"), fetch_redirect_response=False)

    def test_get_also_logs_out(self):
        self.client.login(email="logout@example.com", password="pass1234!")
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse("home:home"), fetch_redirect_response=False)


class ProfileViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse("users:profile")
        self.user = make_user("profile@example.com")

    def test_unauthenticated_redirects(self):
        response = self.client.get(self.url)
        self.assertIn(response.status_code, [302])

    @patch("siteapps.users.views.BackendAPIClient")
    def test_authenticated_renders_profile(self, mock_client_class):
        mock_api = MagicMock()
        mock_api.get_profile.return_value = {"display_name": "Profile User"}
        mock_client_class.return_value = mock_api

        self.client.login(email="profile@example.com", password="pass1234!")
        session = self.client.session
        session["backend_api_token"] = "tok"
        session.save()

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.context.get("profile_data"))

    @patch("siteapps.users.views.BackendAPIClient")
    def test_profile_without_token(self, mock_client_class):
        self.client.login(email="profile@example.com", password="pass1234!")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context.get("profile_data"))


class ChangeUsernameViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse("users:change_username")
        self.user = make_user("changename@example.com")

    def _login_with_token(self):
        self.client.login(email="changename@example.com", password="pass1234!")
        session = self.client.session
        session["backend_api_token"] = "tok"
        session.save()

    def test_short_username_error(self):
        self._login_with_token()
        response = self.client.post(self.url, {"new_username": "ab"})
        msgs = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(any("3 character" in m.lower() or "least" in m.lower() for m in msgs))

    @patch("siteapps.users.views.BackendAPIClient")
    def test_successful_username_change(self, mock_client_class):
        self._login_with_token()
        mock_api = MagicMock()
        mock_api.change_username.return_value = True
        mock_client_class.return_value = mock_api

        response = self.client.post(self.url, {"new_username": "NewName"})
        msgs = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(any("updated" in m.lower() or "success" in m.lower() for m in msgs))

    @patch("siteapps.users.views.BackendAPIClient")
    def test_failed_username_change(self, mock_client_class):
        self._login_with_token()
        mock_api = MagicMock()
        mock_api.change_username.return_value = False
        mock_client_class.return_value = mock_api

        response = self.client.post(self.url, {"new_username": "NewName"})
        msgs = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(any("failed" in m.lower() for m in msgs))


class DeleteAccountViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse("users:delete_account")

    def _login_user(self, email="delete@example.com", name="DeleteMe"):
        user = make_user(email, name=name)
        self.client.login(email=email, password="pass1234!")
        session = self.client.session
        session["backend_api_token"] = "tok"
        session.save()
        return user

    def test_wrong_confirmation_shows_error(self):
        self._login_user()
        response = self.client.post(self.url, {"confirmation": "WrongName"})
        msgs = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(any("match" in m.lower() or "confirmation" in m.lower() for m in msgs))

    @patch("siteapps.users.views.BackendAPIClient")
    def test_successful_deletion_logs_out(self, mock_client_class):
        user = self._login_user()
        mock_api = MagicMock()
        mock_api.delete_account.return_value = True
        mock_client_class.return_value = mock_api

        with patch("siteapps.users.views.logout"):
            response = self.client.post(self.url, {"confirmation": user.name})
        self.assertRedirects(response, reverse("home:home"), fetch_redirect_response=False)

    @patch("siteapps.users.views.BackendAPIClient")
    def test_failed_deletion_shows_error(self, mock_client_class):
        user = self._login_user()
        mock_api = MagicMock()
        mock_api.delete_account.return_value = False
        mock_client_class.return_value = mock_api

        response = self.client.post(self.url, {"confirmation": user.name})
        msgs = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(any("failed" in m.lower() for m in msgs))


class PasswordResetViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse("users:password_reset")

    def test_renders_form(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_missing_email_shows_error(self):
        response = self.client.post(self.url, {"email": ""})
        msgs = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(any("email" in m.lower() or "required" in m.lower() for m in msgs))

    @patch("siteapps.users.views.BackendAPIClient")
    def test_valid_email_redirects_to_login(self, mock_client_class):
        mock_api = MagicMock()
        mock_api.request_password_reset.return_value = True
        mock_client_class.return_value = mock_api

        response = self.client.post(self.url, {"email": "user@example.com"})
        self.assertRedirects(response, reverse("users:login"), fetch_redirect_response=False)

    @patch("siteapps.users.views.BackendAPIClient")
    def test_unknown_email_redirects_without_revealing(self, mock_client_class):
        mock_api = MagicMock()
        mock_api.request_password_reset.return_value = False
        mock_client_class.return_value = mock_api

        response = self.client.post(self.url, {"email": "unknown@example.com"})
        self.assertRedirects(response, reverse("users:login"), fetch_redirect_response=False)


class ResendVerificationViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse("users:resend_verification")
        self.user = make_user("verify@example.com")

    def _login_with_token(self):
        self.client.login(email="verify@example.com", password="pass1234!")
        session = self.client.session
        session["backend_api_token"] = "tok"
        session.save()

    def test_no_token_redirects_to_login(self):
        self.client.login(email="verify@example.com", password="pass1234!")
        response = self.client.post(self.url)
        msgs = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(any("authentication" in m.lower() or "required" in m.lower() for m in msgs))

    @patch("siteapps.users.views.requests")
    def test_successful_resend(self, mock_requests):
        self._login_with_token()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_requests.post.return_value = mock_response

        response = self.client.post(self.url)
        msgs = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(any("sent" in m.lower() or "email" in m.lower() for m in msgs))

    @patch("siteapps.users.views.requests")
    def test_failed_resend_shows_error(self, mock_requests):
        self._login_with_token()
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_requests.post.return_value = mock_response

        response = self.client.post(self.url)
        msgs = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(any("failed" in m.lower() for m in msgs))

    @patch("siteapps.users.views.requests")
    def test_request_exception_shows_error(self, mock_requests):
        self._login_with_token()
        mock_requests.post.side_effect = Exception("Connection error")

        response = self.client.post(self.url)
        msgs = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(any("failed" in m.lower() for m in msgs))


# ---------------------------------------------------------------------------
# BackendAPIClient tests
# ---------------------------------------------------------------------------


class BackendAPIClientTests(TestCase):
    def setUp(self):
        from siteapps.users.api_client import BackendAPIClient

        self.BackendAPIClient = BackendAPIClient

    @patch("siteapps.users.api_client.requests")
    def test_get_success(self, mock_requests):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"key": "value"}
        mock_requests.get.return_value = mock_resp

        client = self.BackendAPIClient(auth_token="tok")
        result = client.get("/some/endpoint/")
        self.assertEqual(result, {"key": "value"})

    @patch("siteapps.users.api_client.requests")
    def test_get_non_200_returns_none(self, mock_requests):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_requests.get.return_value = mock_resp

        client = self.BackendAPIClient()
        result = client.get("/nonexistent/")
        self.assertIsNone(result)

    @patch("siteapps.users.api_client.requests")
    def test_get_request_exception_returns_none(self, mock_requests):
        mock_requests.get.side_effect = requests_lib.exceptions.ConnectionError("down")
        mock_requests.exceptions.RequestException = requests_lib.exceptions.RequestException
        client = self.BackendAPIClient()
        result = client.get("/endpoint/")
        self.assertIsNone(result)

    @patch("siteapps.users.api_client.requests")
    def test_post_success_200(self, mock_requests):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '{"status": "ok"}'
        mock_resp.json.return_value = {"status": "ok"}
        mock_requests.post.return_value = mock_resp

        client = self.BackendAPIClient(auth_token="tok")
        result = client.post("/endpoint/", {"data": 1})
        self.assertEqual(result, {"status": "ok"})

    @patch("siteapps.users.api_client.requests")
    def test_post_success_201_empty_body(self, mock_requests):
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.text = ""
        mock_requests.post.return_value = mock_resp

        client = self.BackendAPIClient(auth_token="tok")
        result = client.post("/endpoint/", {})
        self.assertEqual(result, {"status": "success"})

    @patch("siteapps.users.api_client.requests")
    def test_post_non_200_returns_none(self, mock_requests):
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_requests.post.return_value = mock_resp

        client = self.BackendAPIClient()
        result = client.post("/endpoint/", {})
        self.assertIsNone(result)

    @patch("siteapps.users.api_client.requests")
    def test_post_request_exception_returns_none(self, mock_requests):
        mock_requests.post.side_effect = requests_lib.exceptions.ConnectionError("down")
        mock_requests.exceptions.RequestException = requests_lib.exceptions.RequestException
        client = self.BackendAPIClient()
        result = client.post("/endpoint/", {})
        self.assertIsNone(result)

    @patch("siteapps.users.api_client.requests")
    def test_register_user_success(self, mock_requests):
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {"email": "new@example.com"}
        mock_requests.post.return_value = mock_resp

        client = self.BackendAPIClient()
        success, data = client.register_user("new@example.com", "password1234")
        self.assertTrue(success)

    @patch("siteapps.users.api_client.requests")
    def test_register_user_failure(self, mock_requests):
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.headers = {"content-type": "application/json"}
        mock_resp.json.return_value = {"email": ["Email already exists."]}
        mock_requests.post.return_value = mock_resp

        client = self.BackendAPIClient()
        success, error = client.register_user("dup@example.com", "password1234")
        self.assertFalse(success)
        self.assertIn("Email already exists.", error)

    @patch("siteapps.users.api_client.requests")
    def test_register_user_connection_error(self, mock_requests):
        mock_requests.post.side_effect = requests_lib.exceptions.ConnectionError("down")
        mock_requests.exceptions.RequestException = requests_lib.exceptions.RequestException
        client = self.BackendAPIClient()
        success, error = client.register_user("test@example.com", "pass")
        self.assertFalse(success)
        self.assertIn("connect", error.lower())

    @patch("siteapps.users.api_client.requests")
    def test_logout_success(self, mock_requests):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_requests.post.return_value = mock_resp

        client = self.BackendAPIClient(auth_token="tok")
        result = client.logout()
        self.assertTrue(result)

    @patch("siteapps.users.api_client.requests")
    def test_logout_failure(self, mock_requests):
        mock_requests.post.side_effect = requests_lib.exceptions.ConnectionError()
        mock_requests.exceptions.RequestException = requests_lib.exceptions.RequestException
        client = self.BackendAPIClient(auth_token="tok")
        result = client.logout()
        self.assertFalse(result)

    @patch("siteapps.users.api_client.requests")
    def test_get_profile_success(self, mock_requests):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"display_name": "John"}
        mock_requests.get.return_value = mock_resp

        client = self.BackendAPIClient(auth_token="tok")
        result = client.get_profile()
        self.assertEqual(result["display_name"], "John")

    @patch("siteapps.users.api_client.requests")
    def test_get_profile_failure(self, mock_requests):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_requests.get.return_value = mock_resp

        client = self.BackendAPIClient()
        result = client.get_profile()
        self.assertIsNone(result)

    @patch("siteapps.users.api_client.requests")
    def test_headers_include_auth_token(self, mock_requests):
        client = self.BackendAPIClient(auth_token="mytoken123")
        self.assertIn("Authorization", client.headers)
        self.assertEqual(client.headers["Authorization"], "Token mytoken123")

    def test_headers_without_token(self):
        client = self.BackendAPIClient()
        self.assertNotIn("Authorization", client.headers)
