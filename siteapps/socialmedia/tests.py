import json

from allauth.account.models import EmailAddress
from dateutil import parser
from django.test import TestCase
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient, force_authenticate

from siteapps.socialmedia.models import InappropriateContentReport, Media, MediaPost, TextComment
from siteapps.species.models import SpeciesName
from siteapps.users.models import BannedEmail, User

# Create your tests here.


class SocialMediaPostAPITestCase(TestCase):
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
        _ = self.client.credentials(HTTP_AUTHORIZATION="Token " + token)

        # Request data for social media create API
        SpeciesName.objects.create(name="Acorn Woodpecker", scientific_name="a scientific name")
        self.create_post_data = (
            {
                "postTitle": "This is a new post!",
                "latitude": -1.23,
                "longitude": 4.56,
                "privacySetting": "public",
                "geocodedLocationCountry": "United States",
                "geocodedLocationZipCode": "12345",
                "encounterDatetime": "March 22, 2024 12:38 PM",
                "accuracyMeters": 50,
                "species": "Acorn Woodpecker",
            },
        )

    def test_create_post_no_media(self):
        response = self.client.post("/socialmedia/api/posts/create/", self.create_post_data, format="json")

        self.assertEqual(response.status_code, 201)

        post_obj = MediaPost.objects.filter(created_by=self.user).first()

        # Check the proper fields are populated
        self.assertIsNotNone(post_obj.created_by)

        self.assertEqual(post_obj.geoprivacy, self.create_post_data[0].get("privacySetting"))
        self.assertEqual(post_obj.public_location_latitude, self.create_post_data[0].get("latitude"))
        self.assertEqual(post_obj.public_location_longitude, self.create_post_data[0].get("longitude"))
        self.assertEqual(post_obj.geocoded_location_country, self.create_post_data[0].get("geocodedLocationCountry"))

    def test_get_feed_recent_posts(self):
        # Create a few posts
        for _num in range(0, 23):
            self.client.post("/socialmedia/api/posts/create/", self.create_post_data, format="json")

        self.client.post("/socialmedia/api/feed/get/", {}, format="json")

        _ = self.client.post("/socialmedia/api/feed/get/?random_arg=12345", {"zipCode": "12345"}, format="json")

        response = self.client.post(
            "/socialmedia/api/feed/get/?random_arg=12345&offset=10", {"zipCode": "12345"}, format="json"
        )

        self.assertEqual(response.status_code, 200)

    def test_get_comments(self):
        # Create a few posts
        self.client.post("/socialmedia/api/posts/create/", self.create_post_data, format="json")

        self.client.post(
            "/socialmedia/api/comments/create/",
            {"parentPostId": MediaPost.objects.all().first().id, "commentText": "Hello there!"},
            format="json",
        )

        _ = self.client.post(
            "/socialmedia/api/posts/responses/get/noauth",
            {"mediaPostId": MediaPost.objects.all().first().id},
            format="json",
        )

    def test_get_comments_with_pagination(self):
        # Create a post
        self.client.post("/socialmedia/api/posts/create/", self.create_post_data, format="json")
        post_id = MediaPost.objects.all().first().id

        # Create a large number of comments for the post
        num_comments = 20
        for i in range(num_comments):
            self.client.post(
                "/socialmedia/api/comments/create/",
                {"parentPostId": post_id, "commentText": f"Test Comment {i + 1}"},
                format="json",
            )

        # Define page size for testing pagination
        page_size = 10

        # Request the first page of comments
        response_page_1 = self.client.post(
            "/socialmedia/api/posts/responses/get/noauth",
            {"mediaPostId": post_id, "page": 1, "page_size": page_size},
            format="json",
        )

        # Request the second page of comments
        response_page_2 = self.client.post(
            "/socialmedia/api/posts/responses/get/noauth",
            {"mediaPostId": post_id, "page": 2, "page_size": page_size},
            format="json",
        )

        # Assertions to check that pagination works
        self.assertEqual(response_page_1.status_code, 200)
        self.assertEqual(response_page_2.status_code, 200)

        # Verify the number of comments on each page
        self.assertEqual(len(response_page_1.data["comments"]), page_size)
        self.assertEqual(len(response_page_2.data["comments"]), page_size)

        # Confirm that there are more pages after the first one
        self.assertTrue(response_page_1.data["has_next"])
        self.assertTrue(response_page_2.data["has_previous"])
        print(response_page_1.data["comments"])
        # Ensure the comments retrieved on the two pages are distinct
        first_page_comments = set(comment["id"] for comment in response_page_1.data["comments"])  # noqa: C401
        second_page_comments = set(comment["id"] for comment in response_page_2.data["comments"])  # noqa: C401
        self.assertTrue(first_page_comments.isdisjoint(second_page_comments), "Comments should be unique across pages.")

    def test_report_posts(self):
        # Create a post
        self.client.post("/socialmedia/api/posts/create/", self.create_post_data, format="json")

        self.client.post(
            "/socialmedia/api/comments/create/",
            {"parentPostId": MediaPost.objects.all().first().id, "commentText": "Hello there!"},
            format="json",
        )

        _ = self.client.post(
            "/socialmedia/api/posts/reports/create",
            {"contentId": MediaPost.objects.all().first().id, "contentType": "MediaPost"},
            format="json",
        )

        self.user.is_staff = True
        self.user.save()

        _ = self.client.post(
            "/socialmedia/api/posts/reports/create",
            {"contentId": TextComment.objects.all().first().id, "contentType": "TextComment"},
            format="json",
        )

        response = self.client.get(
            "/socialmedia/api/posts/reports/review",
            format="json",
        )

        _ = self.client.post(
            "/socialmedia/api/posts/reports/ban",
            {"reportId": json.loads(response.content)["report_id"], "banReason": "Did a bad thing."},
            format="json",
        )

        _ = self.client.get(
            "/socialmedia/api/posts/reports/review",
        )

    def test_banned_user_create_media_post(self):
        BannedEmail.objects.create(email=self.user.email)

        response = self.client.post("/socialmedia/api/posts/create/", self.create_post_data, format="json")

        self.assertEqual(response.status_code, 405)
        self.assertFalse(MediaPost.objects.filter(created_by__email=self.user.email).exists())

    def test_like_comment(self):
        # Create a post
        self.client.post("/socialmedia/api/posts/create/", self.create_post_data, format="json")
        post_id = MediaPost.objects.all().first().id

        # Create a comment
        self.client.post(
            "/socialmedia/api/comments/create/",
            {"parentPostId": post_id, "commentText": "Test Comment"},
            format="json",
        )

        comment_id = TextComment.objects.all().first().id

        # Like the comment
        response = self.client.post(
            "/socialmedia/api/comments/like/", {"commentId": str(comment_id)}, format="json"
        )

        self.assertEqual(response.status_code, 200)

        # Verify the comment is liked by the user
        comment = TextComment.objects.get(id=comment_id)
        self.assertTrue(comment.upvoted_by.filter(id=self.user.id).exists())

        # Unlike the comment
        response = self.client.post(
            "/socialmedia/api/comments/like/", {"commentId": str(comment_id)}, format="json"
        )

        self.assertEqual(response.status_code, 200)

        # Verify the comment is not liked by the user
        comment = TextComment.objects.get(id=comment_id)
        self.assertFalse(comment.upvoted_by.filter(id=self.user.id).exists())

    def test_get_comments_with_like_info(self):
        # Create a post
        self.client.post("/socialmedia/api/posts/create/", self.create_post_data, format="json")
        post_id = MediaPost.objects.all().first().id

        # Create some comments
        for i in range(3):
            self.client.post(
                "/socialmedia/api/comments/create/",
                {"parentPostId": post_id, "commentText": f"Test Comment {i + 1}"},
                format="json",
            )

        # Like the first comment
        first_comment_id = TextComment.objects.all().first().id
        self.client.post("/socialmedia/api/comments/like/", {"commentId": str(first_comment_id)}, format="json")

        # Get post responses with like info
        response = self.client.post(
            "/socialmedia/api/posts/responses/get/auth", {"mediaPostId": str(post_id)}, format="json"
        )

        self.assertEqual(response.status_code, 200)
        comments = response.data["comments"]

        # Verify that comments have like_count and liked_by_current_user fields
        for comment in comments:
            self.assertIn("like_count", comment)
            self.assertIn("liked_by_current_user", comment)

        # Verify the first comment is liked
        first_comment = next(c for c in comments if c["id"] == str(first_comment_id))
        self.assertEqual(first_comment["like_count"], 1)
        self.assertTrue(first_comment["liked_by_current_user"])
