import os

import requests
from allauth.account.models import EmailAddress
from dateutil import parser
from django.test import TestCase
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient, force_authenticate

from siteapps.socialmedia.models import Media, MediaPost, TextComment
from siteapps.species.models import SpeciesName
from siteapps.users.models import User


# Create your tests here.
class MapboxAPITestCase(TestCase):
    def setUp(self):
        # Setup a test account
        test_email = "jnovak@example.com"
        test_password = "letmein"

        self.user = User.objects.create(email=test_email)
        self.user.set_password(test_password)
        self.user.is_superuser = True
        self.user.save()

        self.client = APIClient()
        self.client.login(email=test_email, password=test_password)

        # Create a local auth token for the test user
        token, _ = Token.objects.get_or_create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION="Token " + token.key)

        # Also authenticate with backend API to get backend token for proxied requests
        backend_api_url = os.environ.get("BACKEND_API_URL", "http://localhost:8000")
        backend_login_response = requests.post(
            f"{backend_api_url}/v1/users/login/", json={"email": test_email, "password": test_password}
        )
        self.backend_token = backend_login_response.json()["key"]

    def test_search_suggestions(self):
        response = self.client.post("/mapbox/api/search_suggestions/", {"searchText": "Felidae"}, format="json")
        print(response.content)
        self.assertEqual(response.status_code, 200)

    def test_geocode(self):
        response = self.client.post(
            "/mapbox/api/geocode/",
            {"address": "Franklin Canyon Rd @ Alhambra Ave, Martinez, California 94553, United States"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)

    def test_reverse_geocode(self):
        # Test reverse geocoding with San Francisco coordinates
        response = self.client.post(
            "/mapbox/api/reverse_geocode/",
            {"latitude": 37.7749, "longitude": -122.4194},
            format="json",
        )

        # Should return 200 with location data
        self.assertEqual(response.status_code, 200)
        
        # Response should contain location fields
        data = response.json()
        self.assertIn("locality", data)
        self.assertIn("state", data)
        self.assertIn("country", data)
        self.assertIn("zip_code", data)
