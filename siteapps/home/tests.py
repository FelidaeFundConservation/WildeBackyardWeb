from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse


class PageTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = get_user_model().objects.create_user(
            email="test@example.com", password="testpass123", name="Test User"
        )

    def check_single_page(self, page):
        url = reverse(page)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_main_pages(self):
        self.check_single_page("users:register")
        self.check_single_page("users:login")

        self.client.login(email="test@example.com", password="testpass123")

        self.check_single_page("home:home")
        self.check_single_page("users:profile")
