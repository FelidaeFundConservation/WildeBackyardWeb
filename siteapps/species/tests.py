import os

import requests
from allauth.account.models import EmailAddress
from dateutil import parser
from django.conf import settings
from django.test import TestCase
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient, force_authenticate

from siteapps.socialmedia.models import Media, MediaPost, TextComment
from siteapps.species.models import SpeciesName
from siteapps.users.models import User

# Create your tests here.


class SpeciesAPITestCase(TestCase):
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
        backend_login_response = requests.post(
            f"{settings.BACKEND_API_URL}/v1/users/login/", json={"email": test_email, "password": test_password}
        )
        self.backend_token = backend_login_response.json()["key"]

    def test_get_species_names(self):
        SpeciesName.objects.create(name="Test", scientific_name="Science")
        response = self.client.get("/species/api/names/get/", {}, format="json")

        # Validate the output
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"species_names": ["Test"]})

    def test_create_species_name(self):
        response = self.client.post("/species/api/names/create/", {"name": "speCieS"}, format="json")

        # Validate the response and the database entry
        self.assertEqual(response.status_code, 201)
        self.assertTrue(SpeciesName.objects.filter(name="Species").exists())
