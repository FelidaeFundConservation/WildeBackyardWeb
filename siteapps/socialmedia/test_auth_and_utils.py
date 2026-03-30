"""Tests for auth backend, mixins, and sightings utils."""

from unittest.mock import MagicMock, patch

from django.conf import settings
from django.test import RequestFactory, TestCase

from siteapps.users.models import User

# ---------------------------------------------------------------------------
# BackendAPIAuthBackend Tests
# ---------------------------------------------------------------------------


class BackendAPIAuthBackendTests(TestCase):
    def setUp(self):
        from siteapps.users.auth_backend import BackendAPIAuthBackend

        self.backend = BackendAPIAuthBackend()

    def test_returns_none_without_email(self):
        result = self.backend.authenticate(None, email=None, password="pass")
        self.assertIsNone(result)

    def test_returns_none_without_password(self):
        result = self.backend.authenticate(None, email="test@example.com", password=None)
        self.assertIsNone(result)

    @patch("siteapps.users.auth_backend.requests")
    def test_successful_authentication_creates_user(self, mock_requests):
        login_resp = MagicMock()
        login_resp.status_code = 200
        login_resp.json.return_value = {"key": "tok123"}

        profile_resp = MagicMock()
        profile_resp.status_code = 200
        profile_resp.json.return_value = {
            "display_name": "Jane Doe",
            "is_staff": False,
            "is_superuser": False,
        }

        mock_requests.post.return_value = login_resp
        mock_requests.get.return_value = profile_resp

        factory = RequestFactory()
        request = factory.get("/")
        request.session = {}

        user = self.backend.authenticate(request, email="jane@example.com", password="secret")
        self.assertIsNotNone(user)
        self.assertEqual(user.email, "jane@example.com")
        self.assertEqual(request.session.get("backend_api_token"), "tok123")

    @patch("siteapps.users.auth_backend.requests")
    def test_updates_existing_user(self, mock_requests):
        User.objects.create_user(email="existing@example.com", password="old", name="OldName")

        login_resp = MagicMock()
        login_resp.status_code = 200
        login_resp.json.return_value = {"key": "newtok"}

        profile_resp = MagicMock()
        profile_resp.status_code = 200
        profile_resp.json.return_value = {
            "display_name": "UpdatedName",
            "is_staff": True,
            "is_superuser": False,
        }

        mock_requests.post.return_value = login_resp
        mock_requests.get.return_value = profile_resp

        factory = RequestFactory()
        request = factory.get("/")
        request.session = {}

        user = self.backend.authenticate(request, email="existing@example.com", password="any")
        self.assertEqual(user.name, "UpdatedName")
        self.assertTrue(user.is_staff)

    @patch("siteapps.users.auth_backend.requests")
    def test_no_token_in_response_returns_none(self, mock_requests):
        login_resp = MagicMock()
        login_resp.status_code = 200
        login_resp.json.return_value = {}  # No "key"
        mock_requests.post.return_value = login_resp

        result = self.backend.authenticate(None, email="a@b.com", password="p")
        self.assertIsNone(result)

    @patch("siteapps.users.auth_backend.requests")
    def test_login_failure_returns_none(self, mock_requests):
        login_resp = MagicMock()
        login_resp.status_code = 400
        mock_requests.post.return_value = login_resp

        result = self.backend.authenticate(None, email="a@b.com", password="bad")
        self.assertIsNone(result)

    @patch("siteapps.users.auth_backend.requests")
    def test_profile_fetch_failure_returns_none(self, mock_requests):
        login_resp = MagicMock()
        login_resp.status_code = 200
        login_resp.json.return_value = {"key": "tok"}

        profile_resp = MagicMock()
        profile_resp.status_code = 500
        mock_requests.post.return_value = login_resp
        mock_requests.get.return_value = profile_resp

        result = self.backend.authenticate(None, email="a@b.com", password="p")
        self.assertIsNone(result)

    @patch("siteapps.users.auth_backend.requests")
    def test_connection_error_returns_none(self, mock_requests):
        import requests as req_lib

        mock_requests.post.side_effect = req_lib.exceptions.ConnectionError("down")
        mock_requests.exceptions.RequestException = req_lib.exceptions.RequestException
        result = self.backend.authenticate(None, email="a@b.com", password="p")
        self.assertIsNone(result)

    def test_get_user_found(self):
        user = User.objects.create_user(email="found@example.com", password="p", name="Found")
        result = self.backend.get_user(user.pk)
        self.assertEqual(result, user)

    def test_get_user_not_found(self):
        import uuid

        result = self.backend.get_user(uuid.uuid4())
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# Mixin Tests
# ---------------------------------------------------------------------------


class LatLngValidationMixinTests(TestCase):
    def setUp(self):
        from siteapps.socialmedia.mixins import LatLngValidationMixin

        self.validate = LatLngValidationMixin.validate_latitude_longitude

    def test_both_missing_returns_400(self):
        result = self.validate(None, None)
        self.assertIsNotNone(result)
        self.assertEqual(result.status_code, 400)

    def test_lat_missing_returns_400(self):
        result = self.validate(None, "45.0")
        self.assertIsNotNone(result)
        self.assertEqual(result.status_code, 400)

    def test_lon_missing_returns_400(self):
        result = self.validate("45.0", None)
        self.assertIsNotNone(result)
        self.assertEqual(result.status_code, 400)

    def test_invalid_lat_returns_400(self):
        result = self.validate("200", "45.0")  # > 90
        self.assertIsNotNone(result)
        self.assertEqual(result.status_code, 400)

    def test_invalid_lon_returns_400(self):
        result = self.validate("45.0", "200")  # > 180
        self.assertIsNotNone(result)
        self.assertEqual(result.status_code, 400)

    def test_both_invalid_returns_400(self):
        result = self.validate("200", "200")
        self.assertIsNotNone(result)
        self.assertEqual(result.status_code, 400)

    def test_valid_returns_none(self):
        result = self.validate("45.0", "-93.0")
        self.assertIsNone(result)

    def test_boundary_lat_exactly_90_invalid(self):
        result = self.validate("90", "0")
        self.assertIsNotNone(result)

    def test_boundary_lon_exactly_180_invalid(self):
        result = self.validate("0", "180")
        self.assertIsNotNone(result)


class PrivacySettingValidationMixinTests(TestCase):
    def setUp(self):
        from siteapps.socialmedia.mixins import PrivacySettingValidationMixin

        self.validate = PrivacySettingValidationMixin.validate_privacy_setting

    def test_none_returns_400(self):
        result = self.validate(None)
        self.assertIsNotNone(result)
        self.assertEqual(result.status_code, 400)

    def test_invalid_string_returns_400(self):
        result = self.validate("secret")
        self.assertIsNotNone(result)
        self.assertEqual(result.status_code, 400)

    def test_public_returns_none(self):
        result = self.validate(settings.PRIVACY_SETTING_PUBLIC)
        self.assertIsNone(result)

    def test_obscured_returns_none(self):
        result = self.validate(settings.PRIVACY_SETTING_OBSCURED)
        self.assertIsNone(result)

    def test_private_returns_none(self):
        result = self.validate(settings.PRIVACY_SETTING_PRIVATE)
        self.assertIsNone(result)


class PostInputsValidationMixinTests(TestCase):
    def setUp(self):
        from siteapps.socialmedia.mixins import PostInputsValidationMixin

        self.validate = PostInputsValidationMixin.validate_arguments_exist

    def _call(self, **overrides):
        defaults = {
            "privacy_setting": settings.PRIVACY_SETTING_PUBLIC,
            "encounter_datetime": "2024-01-01",
            "accuracy_meters": 5,
            "obfuscation_kilometers": None,
            "obfuscation_box_corners": [],
            "geocoded_location_country": "US",
            "post_title": "My Post",
        }
        defaults.update(overrides)
        return self.validate(**defaults)

    def test_missing_datetime_returns_400(self):
        result = self._call(encounter_datetime=None)
        self.assertIsNotNone(result)
        self.assertEqual(result.status_code, 400)

    def test_missing_accuracy_returns_400(self):
        result = self._call(accuracy_meters=None)
        self.assertIsNotNone(result)
        self.assertEqual(result.status_code, 400)

    def test_missing_title_returns_400(self):
        result = self._call(post_title=None)
        self.assertIsNotNone(result)
        self.assertEqual(result.status_code, 400)

    def test_obscured_missing_km_returns_400(self):
        result = self._call(
            privacy_setting=settings.PRIVACY_SETTING_OBSCURED,
            obfuscation_kilometers=None,
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.status_code, 400)

    def test_obscured_km_out_of_range_returns_400(self):
        result = self._call(
            privacy_setting=settings.PRIVACY_SETTING_OBSCURED,
            obfuscation_kilometers=15,
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.status_code, 400)

    def test_obscured_wrong_box_corners_count_returns_400(self):
        result = self._call(
            privacy_setting=settings.PRIVACY_SETTING_OBSCURED,
            obfuscation_kilometers=5,
            obfuscation_box_corners=[1, 2, 3, 4],  # Only 4, need 8
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.status_code, 400)

    def test_obscured_valid_inputs_returns_none(self):
        result = self._call(
            privacy_setting=settings.PRIVACY_SETTING_OBSCURED,
            obfuscation_kilometers=5,
            obfuscation_box_corners=[1, 2, 3, 4, 5, 6, 7, 8],
        )
        self.assertIsNone(result)

    def test_public_all_valid_returns_none(self):
        result = self._call()
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# Reverse Geocoding Utility Tests
# ---------------------------------------------------------------------------


class ReverseGeocodeTests(TestCase):
    def setUp(self):
        from siteapps.sightings.utils import reverse_geocode_with_nominatim

        self.geocode = reverse_geocode_with_nominatim

    @patch("siteapps.sightings.utils.requests")
    def test_successful_city_geocode(self, mock_requests):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "address": {
                "city": "Portland",
                "state": "Oregon",
                "country": "United States",
                "postcode": "97201",
            }
        }
        mock_requests.get.return_value = mock_resp

        result = self.geocode(45.5, -122.7)
        self.assertIsNotNone(result)
        self.assertEqual(result["locality"], "Portland")
        self.assertEqual(result["state"], "Oregon")
        self.assertEqual(result["country"], "United States")
        self.assertEqual(result["zip_code"], "97201")

    @patch("siteapps.sightings.utils.requests")
    def test_falls_back_to_town(self, mock_requests):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "address": {
                "town": "Smalltown",
                "state": "Montana",
                "country": "United States",
            }
        }
        mock_requests.get.return_value = mock_resp

        result = self.geocode(46.0, -112.0)
        self.assertEqual(result["locality"], "Smalltown")

    @patch("siteapps.sightings.utils.requests")
    def test_falls_back_to_village(self, mock_requests):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "address": {
                "village": "Tinyville",
                "country": "United States",
            }
        }
        mock_requests.get.return_value = mock_resp

        result = self.geocode(46.0, -112.0)
        self.assertEqual(result["locality"], "Tinyville")

    @patch("siteapps.sightings.utils.requests")
    def test_non_200_returns_none(self, mock_requests):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_requests.get.return_value = mock_resp

        result = self.geocode(0.0, 0.0)
        self.assertIsNone(result)

    @patch("siteapps.sightings.utils.requests")
    def test_request_exception_returns_none(self, mock_requests):
        import requests as req_lib

        mock_requests.get.side_effect = req_lib.exceptions.ConnectionError("down")
        mock_requests.exceptions.RequestException = req_lib.exceptions.RequestException

        result = self.geocode(0.0, 0.0)
        self.assertIsNone(result)
