import json

from allauth.account.models import EmailAddress
from dateutil import parser
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
        test_email = "wildebackyard@fakeemail.com"
        test_password = "fakepassword"

        self.user = User.objects.create(email=test_email)
        self.user.set_password(test_password)
        self.user.is_superuser = True
        self.user.save()

        self.client = APIClient()
        self.client.login(email=test_email, password=test_password)

        # Get the auth token from the test account
        login_response = self.client.post(
            "/users/login/", {"email": test_email, "password": test_password}, format="json"
        )

        token = json.loads(login_response.content)["key"]
        headers = self.client.credentials(HTTP_AUTHORIZATION="Token " + token)

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
