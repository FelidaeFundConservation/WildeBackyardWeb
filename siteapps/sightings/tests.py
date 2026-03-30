"""Tests for siteapps/sightings/views.py"""

import json
import uuid
from unittest.mock import MagicMock, patch

from django.contrib.messages import get_messages
from django.test import Client, TestCase
from django.urls import reverse
from rest_framework.authtoken.models import Token
from rest_framework.test import APIRequestFactory, force_authenticate

from siteapps.users.models import User


def make_user(email="sightings@example.com", is_staff=False):
    user = User.objects.create_user(email=email, password="pass1234!", name="SightUser")
    user.is_staff = is_staff
    user.save()
    return user


FAKE_SIGHTING = {
    "id": str(uuid.uuid4()),
    "title": "Saw a robin",
    "body": None,
    "species": [{"name": "Robin"}],
    "media": None,
    "created_by": "sightuser",
    "encounter_datetime": "2024-03-01T08:00:00Z",
    "additional_info": {},
    "geocoded_location": "Seattle, WA",
    "likes_count": 0,
    "comments_count": 0,
}


class CreateSightingViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = make_user("create_sight@example.com")
        self.url = reverse("sightings:create")

    def _login_with_token(self):
        self.client.login(email=self.user.email, password="pass1234!")
        session = self.client.session
        session["backend_api_token"] = "tok"
        session.save()

    def test_unauthenticated_redirects(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    @patch("siteapps.sightings.views.BackendAPIClient")
    def test_get_renders_form_with_species(self, mock_client_class):
        self._login_with_token()
        mock_api = MagicMock()
        mock_api.get.return_value = {"species_names": ["Robin", "Hawk"]}
        mock_client_class.return_value = mock_api

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["species_list"], ["Robin", "Hawk"])

    @patch("siteapps.sightings.views.BackendAPIClient")
    def test_get_handles_species_api_failure(self, mock_client_class):
        self._login_with_token()
        mock_api = MagicMock()
        mock_api.get.return_value = None
        mock_client_class.return_value = mock_api

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["species_list"], [])

    def test_post_missing_api_token_redirects(self):
        self.client.login(email=self.user.email, password="pass1234!")
        response = self.client.post(
            self.url,
            {
                "post_title": "Test",
                "encounter_date": "2024-01-01",
                "location_latitude": "45.0",
                "location_longitude": "-93.0",
            },
        )
        self.assertRedirects(response, reverse("users:login"), fetch_redirect_response=False)

    @patch("siteapps.sightings.views.BackendAPIClient")
    @patch("siteapps.sightings.views.reverse_geocode_with_nominatim")
    def test_post_missing_title_shows_error(self, mock_geocode, mock_client_class):
        self._login_with_token()
        mock_geocode.return_value = None
        mock_api = MagicMock()
        mock_api.get.return_value = {"species_names": []}
        mock_client_class.return_value = mock_api

        response = self.client.post(
            self.url,
            {
                "encounter_date": "2024-01-01",
                "location_latitude": "45.0",
                "location_longitude": "-93.0",
            },
        )
        msgs = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(any("title" in m.lower() for m in msgs))

    @patch("siteapps.sightings.views.BackendAPIClient")
    @patch("siteapps.sightings.views.reverse_geocode_with_nominatim")
    def test_post_missing_datetime_shows_error(self, mock_geocode, mock_client_class):
        self._login_with_token()
        mock_geocode.return_value = None
        mock_api = MagicMock()
        mock_api.get.return_value = {"species_names": []}
        mock_client_class.return_value = mock_api

        response = self.client.post(
            self.url,
            {
                "post_title": "Bird sighting",
                "location_latitude": "45.0",
                "location_longitude": "-93.0",
            },
        )
        msgs = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(any("date" in m.lower() or "datetime" in m.lower() or "encounter" in m.lower() for m in msgs))

    @patch("siteapps.sightings.views.BackendAPIClient")
    @patch("siteapps.sightings.views.reverse_geocode_with_nominatim")
    def test_post_missing_location_shows_error(self, mock_geocode, mock_client_class):
        self._login_with_token()
        mock_geocode.return_value = None
        mock_api = MagicMock()
        mock_api.get.return_value = {"species_names": []}
        mock_client_class.return_value = mock_api

        response = self.client.post(
            self.url,
            {
                "post_title": "Bird",
                "encounter_date": "2024-01-01",
            },
        )
        msgs = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(any("location" in m.lower() for m in msgs))

    @patch("siteapps.sightings.views.BackendAPIClient")
    @patch("siteapps.sightings.views.reverse_geocode_with_nominatim")
    def test_successful_submission_redirects_to_feed(self, mock_geocode, mock_client_class):
        self._login_with_token()
        mock_geocode.return_value = {
            "locality": "Portland",
            "state": "Oregon",
            "country": "United States",
            "zip_code": "97201",
        }
        mock_api = MagicMock()
        mock_api.get.return_value = {"species_names": ["Robin"]}
        mock_api.post.return_value = {"status": "success"}
        mock_client_class.return_value = mock_api

        response = self.client.post(
            self.url,
            {
                "post_title": "Bird sighting",
                "encounter_date": "2024-01-01",
                "encounter_time": "10:00",
                "location_latitude": "45.5",
                "location_longitude": "-122.7",
                "privacy_setting": "public",
                "location_accuracy_meters": "5",
                "species_list": ["Robin"],
            },
        )
        self.assertRedirects(response, reverse("socialmedia:feed"), fetch_redirect_response=False)

    @patch("siteapps.sightings.views.BackendAPIClient")
    @patch("siteapps.sightings.views.reverse_geocode_with_nominatim")
    def test_api_submission_failure_shows_error(self, mock_geocode, mock_client_class):
        self._login_with_token()
        mock_geocode.return_value = None
        mock_api = MagicMock()
        mock_api.get.return_value = {"species_names": []}
        mock_api.post.return_value = None
        mock_client_class.return_value = mock_api

        response = self.client.post(
            self.url,
            {
                "post_title": "Bird sighting",
                "encounter_date": "2024-01-01",
                "location_latitude": "45.5",
                "location_longitude": "-122.7",
            },
        )
        msgs = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(any("failed" in m.lower() or "error" in m.lower() or "submit" in m.lower() for m in msgs))

    @patch("siteapps.sightings.views.BackendAPIClient")
    @patch("siteapps.sightings.views.reverse_geocode_with_nominatim")
    def test_invalid_coordinates_shows_error(self, mock_geocode, mock_client_class):
        self._login_with_token()
        mock_geocode.return_value = None
        mock_api = MagicMock()
        mock_api.get.return_value = {"species_names": []}
        mock_client_class.return_value = mock_api

        response = self.client.post(
            self.url,
            {
                "post_title": "Bird",
                "encounter_date": "2024-01-01",
                "location_latitude": "not_a_number",
                "location_longitude": "-93.0",
            },
        )
        msgs = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(
            any("latitude" in m.lower() or "invalid" in m.lower() or "longitude" in m.lower() for m in msgs)
        )


class MySightingsViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = make_user("mysight@example.com")
        self.url = reverse("sightings:my_sightings")

    def test_unauthenticated_redirects(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    @patch("siteapps.sightings.views.BackendAPIClient")
    def test_renders_sightings(self, mock_client_class):
        self.client.login(email=self.user.email, password="pass1234!")
        session = self.client.session
        session["backend_api_token"] = "tok"
        session.save()

        mock_api = MagicMock()
        mock_api.post.return_value = {"results": [FAKE_SIGHTING]}
        mock_client_class.return_value = mock_api

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["sightings"]), 1)

    @patch("siteapps.sightings.views.BackendAPIClient")
    def test_api_failure_shows_error(self, mock_client_class):
        self.client.login(email=self.user.email, password="pass1234!")
        session = self.client.session
        session["backend_api_token"] = "tok"
        session.save()

        mock_api = MagicMock()
        mock_api.post.return_value = None
        mock_client_class.return_value = mock_api

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        msgs = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(any("unable" in m.lower() or "error" in m.lower() for m in msgs))

    def test_no_token_renders_empty(self):
        self.client.login(email=self.user.email, password="pass1234!")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["sightings"], [])


class SightingsMapViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = make_user("mapuser@example.com")
        self.url = reverse("sightings:map")

    def test_unauthenticated_redirects(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_renders_map_page(self):
        self.client.login(email=self.user.email, password="pass1234!")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)


class SightingsByBboxViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = make_user("bboxuser@example.com")
        self.url = reverse("sightings:bbox")

    def _login_with_token(self):
        self.client.login(email=self.user.email, password="pass1234!")
        session = self.client.session
        session["backend_api_token"] = "tok"
        session.save()

    def test_get_returns_405(self):
        self._login_with_token()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)

    def test_no_token_returns_401(self):
        self.client.login(email=self.user.email, password="pass1234!")
        response = self.client.post(
            self.url,
            json.dumps({"minLatitude": 45.0, "maxLatitude": 46.0, "minLongitude": -94.0, "maxLongitude": -93.0}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)

    def test_invalid_json_returns_400(self):
        self._login_with_token()
        response = self.client.post(self.url, "not json", content_type="application/json")
        self.assertEqual(response.status_code, 400)

    @patch("siteapps.sightings.views.BackendAPIClient")
    def test_success_returns_geojson(self, mock_client_class):
        self._login_with_token()
        mock_api = MagicMock()
        mock_api.post.return_value = {
            "results": [
                {
                    "id": str(uuid.uuid4()),
                    "latitude": 45.5,
                    "longitude": -93.0,
                    "title": "Bird",
                    "species": "Robin",
                    "encounter_datetime": "2024-01-01",
                    "geocoded_location": "MN",
                }
            ],
            "count": 1,
        }
        mock_client_class.return_value = mock_api

        response = self.client.post(
            self.url,
            json.dumps({"minLatitude": 45.0, "maxLatitude": 46.0, "minLongitude": -94.0, "maxLongitude": -93.0}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["type"], "FeatureCollection")
        self.assertEqual(len(data["features"]), 1)

    @patch("siteapps.sightings.views.BackendAPIClient")
    def test_api_failure_returns_502(self, mock_client_class):
        self._login_with_token()
        mock_api = MagicMock()
        mock_api.post.return_value = None
        mock_client_class.return_value = mock_api

        response = self.client.post(
            self.url,
            json.dumps({"minLatitude": 45.0, "maxLatitude": 46.0}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 502)

    @patch("siteapps.sightings.views.BackendAPIClient")
    def test_skips_posts_without_coordinates(self, mock_client_class):
        self._login_with_token()
        mock_api = MagicMock()
        mock_api.post.return_value = {
            "results": [
                {"id": "1", "latitude": None, "longitude": None, "title": "No coords"},
                {"id": "2", "latitude": 45.5, "longitude": -93.0, "title": "Has coords"},
            ],
            "count": 2,
        }
        mock_client_class.return_value = mock_api

        response = self.client.post(
            self.url,
            json.dumps({"minLatitude": 45.0, "maxLatitude": 46.0}),
            content_type="application/json",
        )
        data = response.json()
        self.assertEqual(len(data["features"]), 1)


class ReverseGeocodeAPIViewTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = make_user("geocode@example.com")
        self.token, _ = Token.objects.get_or_create(user=self.user)

    def _call(self, data):
        from siteapps.sightings.views import ReverseGeocodeWithNominatim

        request = self.factory.post(
            "/sightings/api/reverse_geocode/",
            json.dumps(data),
            content_type="application/json",
        )
        force_authenticate(request, user=self.user, token=self.token)
        return ReverseGeocodeWithNominatim.as_view()(request)

    def test_missing_lat_lon_returns_400(self):
        response = self._call({})
        self.assertEqual(response.status_code, 400)

    def test_missing_lon_returns_400(self):
        response = self._call({"latitude": 45.0})
        self.assertEqual(response.status_code, 400)

    @patch("siteapps.sightings.views.reverse_geocode_with_nominatim")
    def test_success_returns_location_data(self, mock_geocode):
        mock_geocode.return_value = {
            "locality": "Portland",
            "state": "Oregon",
            "country": "United States",
            "zip_code": "97201",
        }
        response = self._call({"latitude": 45.5, "longitude": -122.7})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["locality"], "Portland")

    @patch("siteapps.sightings.views.reverse_geocode_with_nominatim")
    def test_geocode_failure_returns_500(self, mock_geocode):
        mock_geocode.return_value = None
        response = self._call({"latitude": 0, "longitude": 0})
        self.assertEqual(response.status_code, 500)
