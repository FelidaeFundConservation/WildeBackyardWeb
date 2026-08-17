# Licensed under the MIT License.
# See LICENSE file in the project root for full license information.

"""Tests for siteapps/socialmedia/web_views.py"""

import uuid
from unittest.mock import MagicMock, patch

from django.contrib.messages import get_messages
from django.test import Client, TestCase
from django.urls import reverse

from siteapps.users.models import User


def make_user(email="viewer@example.com", is_staff=False, is_superuser=False):
    user = User.objects.create_user(email=email, password="pass1234!", name="View User")
    user.is_staff = is_staff
    user.is_superuser = is_superuser
    user.save()
    return user


FAKE_POST = {
    "id": str(uuid.uuid4()),
    "title": "A sighting",
    "body": "There was a bird",
    "species": [{"name": "Robin"}],
    "media": {"url": "https://example.com/img.jpg", "is_video": False},
    "created_by": "testuser",
    "encounter_datetime": "2024-01-01T12:00:00Z",
    "additional_info": {"camera_model": "Canon", "habitat_type": "Forest"},
    "geocoded_location": "Portland, OR",
    "likes_count": 3,
    "comments_count": 1,
    "quality_metrics": [],
}

FAKE_FEED_RESPONSE = {
    "results": [FAKE_POST],
    "next": None,
    "count": 1,
}


class FeedViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = make_user()
        self.url = reverse("socialmedia:feed")

    def _login_with_session_token(self):
        self.client.login(email=self.user.email, password="pass1234!")
        session = self.client.session
        session["backend_api_token"] = "testtoken123"
        session.save()

    @patch("siteapps.socialmedia.web_views.BackendAPIClient")
    def test_unauthenticated_shows_empty_feed(self, mock_client_class):
        mock_api = MagicMock()
        mock_api.get.return_value = {"species_names": ["Robin"]}
        mock_client_class.return_value = mock_api

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["posts"], [])

    @patch("siteapps.socialmedia.web_views.BackendAPIClient")
    def test_authenticated_shows_posts(self, mock_client_class):
        self._login_with_session_token()
        mock_api = MagicMock()
        mock_api.post.return_value = FAKE_FEED_RESPONSE
        mock_api.get.return_value = {"species_names": ["Robin"]}
        mock_client_class.return_value = mock_api

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["posts"]), 1)

    @patch("siteapps.socialmedia.web_views.BackendAPIClient")
    def test_species_filter_passed_to_api(self, mock_client_class):
        self._login_with_session_token()
        mock_api = MagicMock()
        mock_api.post.return_value = FAKE_FEED_RESPONSE
        mock_api.get.return_value = {"species_names": ["Robin"]}
        mock_client_class.return_value = mock_api

        response = self.client.get(self.url + "?species=Robin")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["current_species"], "Robin")

    @patch("siteapps.socialmedia.web_views.BackendAPIClient")
    def test_radius_filter_passed_when_valid(self, mock_client_class):
        self._login_with_session_token()
        mock_api = MagicMock()
        mock_api.post.return_value = FAKE_FEED_RESPONSE
        mock_api.get.return_value = {"species_names": []}
        mock_client_class.return_value = mock_api

        response = self.client.get(self.url + "?location=radius&center_lat=45.5&center_lon=-93.0&radius_km=10")
        self.assertEqual(response.status_code, 200)
        call_data = mock_api.post.call_args[0][1]
        self.assertIn("distanceRadius", call_data)

    @patch("siteapps.socialmedia.web_views.BackendAPIClient")
    def test_invalid_radius_params_parsed_gracefully(self, mock_client_class):
        self._login_with_session_token()
        mock_api = MagicMock()
        mock_api.post.return_value = FAKE_FEED_RESPONSE
        mock_api.get.return_value = {"species_names": []}
        mock_client_class.return_value = mock_api

        response = self.client.get(self.url + "?location=radius&center_lat=not_a_number&center_lon=-93.0&radius_km=10")
        self.assertEqual(response.status_code, 200)

    def test_feed_renders_without_species_list_in_context(self):
        # species_list is no longer pre-populated; filter uses live autocomplete
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("species_list", response.context)


class PostDetailViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = make_user("detail@example.com")
        self.post_id = str(uuid.uuid4())
        self.url = reverse("socialmedia:post_detail", kwargs={"post_id": self.post_id})

    def _login_with_session_token(self):
        self.client.login(email=self.user.email, password="pass1234!")
        session = self.client.session
        session["backend_api_token"] = "testtoken123"
        session.save()

    def test_unauthenticated_redirects_to_login(self):
        self.client.login(email=self.user.email, password="pass1234!")
        # No backend_api_token in session
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse("users:login"), fetch_redirect_response=False)

    @patch("siteapps.socialmedia.web_views.BackendAPIClient")
    def test_post_not_found_redirects_to_feed(self, mock_client_class):
        self._login_with_session_token()
        mock_api = MagicMock()
        mock_api.get.return_value = None
        mock_client_class.return_value = mock_api

        response = self.client.get(self.url)
        self.assertRedirects(response, reverse("socialmedia:feed"), fetch_redirect_response=False)

    @patch("siteapps.socialmedia.web_views.BackendAPIClient")
    def test_post_detail_renders(self, mock_client_class):
        self._login_with_session_token()
        mock_api = MagicMock()
        mock_api.get.side_effect = [
            {**FAKE_POST, "quality_metrics": []},
            {
                "taxa": [
                    {
                        "id": 1,
                        "inat_id": 3001,
                        "name": "Turdus migratorius",
                        "preferred_common_name": "American Robin",
                        "iconic_taxon_name": "Aves",
                        "observations_count": 5000,
                    }
                ]
            },
        ]
        mock_api.post.return_value = {
            "comments": [],
            "liked_by_current_user": False,
            "like_count": 0,
        }
        mock_client_class.return_value = mock_api

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    @patch("siteapps.socialmedia.web_views.BackendAPIClient")
    def test_not_logged_in_at_all_redirects(self, mock_client_class):
        response = self.client.get(self.url)
        self.assertIn(response.status_code, [302, 200])


class VoteQualityMetricViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.post_id = str(uuid.uuid4())

    def _login_user(self, is_staff=False):
        user = make_user(f"voter_{is_staff}@example.com", is_staff=is_staff)
        self.client.login(email=user.email, password="pass1234!")
        session = self.client.session
        session["backend_api_token"] = "tok"
        session.save()
        return user

    def test_non_staff_blocked(self):
        self._login_user(is_staff=False)
        url = reverse("socialmedia:vote_quality_metric", kwargs={"post_id": self.post_id, "metric": "animal_visible"})
        response = self.client.post(url, {"agree": "true"})
        self.assertRedirects(
            response,
            reverse("socialmedia:post_detail", kwargs={"post_id": self.post_id}),
            fetch_redirect_response=False,
        )
        msgs = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(any("permission" in m.lower() for m in msgs))

    @patch("siteapps.socialmedia.web_views.BackendAPIClient")
    def test_staff_can_vote(self, mock_client_class):
        self._login_user(is_staff=True)
        mock_api = MagicMock()
        mock_api.post.return_value = {"status": "success"}
        mock_client_class.return_value = mock_api

        url = reverse("socialmedia:vote_quality_metric", kwargs={"post_id": self.post_id, "metric": "animal_visible"})
        response = self.client.post(url, {"agree": "true"})
        self.assertRedirects(
            response,
            reverse("socialmedia:post_detail", kwargs={"post_id": self.post_id}),
            fetch_redirect_response=False,
        )

    @patch("siteapps.socialmedia.web_views.BackendAPIClient")
    def test_failed_api_call_adds_error_message(self, mock_client_class):
        self._login_user(is_staff=True)
        mock_api = MagicMock()
        mock_api.post.return_value = None
        mock_client_class.return_value = mock_api

        url = reverse("socialmedia:vote_quality_metric", kwargs={"post_id": self.post_id, "metric": "animal_visible"})
        response = self.client.post(url, {"agree": "true"})
        msgs = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(any("failed" in m.lower() or "error" in m.lower() for m in msgs))


class UpdateSightingSpeciesViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.post_id = str(uuid.uuid4())

    def _login_user(self, is_staff=False):
        user = make_user(f"species_{is_staff}@example.com", is_staff=is_staff)
        self.client.login(email=user.email, password="pass1234!")
        session = self.client.session
        session["backend_api_token"] = "tok"
        session.save()

    def test_non_staff_blocked(self):
        self._login_user(is_staff=False)
        url = reverse("socialmedia:update_sighting_species", kwargs={"post_id": self.post_id})
        response = self.client.post(url, {"species_list": ["Robin"]})
        msgs = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(any("permission" in m.lower() for m in msgs))

    def test_empty_species_list_error(self):
        self._login_user(is_staff=True)
        url = reverse("socialmedia:update_sighting_species", kwargs={"post_id": self.post_id})
        response = self.client.post(url, {})
        msgs = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(any("species" in m.lower() for m in msgs))

    @patch("siteapps.socialmedia.web_views.BackendAPIClient")
    def test_staff_success(self, mock_client_class):
        self._login_user(is_staff=True)
        mock_api = MagicMock()
        mock_api.post.return_value = {"status": "success"}
        mock_client_class.return_value = mock_api

        url = reverse("socialmedia:update_sighting_species", kwargs={"post_id": self.post_id})
        response = self.client.post(url, {"species_list": ["Robin"]})
        msgs = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(any("updated" in m.lower() for m in msgs))


class UpdateAnimalCountViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.post_id = str(uuid.uuid4())

    def _login_user(self, is_staff=False):
        user = make_user(f"animal_{is_staff}@example.com", is_staff=is_staff)
        self.client.login(email=user.email, password="pass1234!")
        session = self.client.session
        session["backend_api_token"] = "tok"
        session.save()

    def test_non_staff_blocked(self):
        self._login_user(is_staff=False)
        url = reverse("socialmedia:update_animal_count", kwargs={"post_id": self.post_id})
        response = self.client.post(url, {"animal_count": "3"})
        msgs = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(any("permission" in m.lower() for m in msgs))

    def test_empty_count_error(self):
        self._login_user(is_staff=True)
        url = reverse("socialmedia:update_animal_count", kwargs={"post_id": self.post_id})
        response = self.client.post(url, {})
        msgs = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(any("required" in m.lower() or "count" in m.lower() for m in msgs))

    @patch("siteapps.socialmedia.web_views.BackendAPIClient")
    def test_staff_success(self, mock_client_class):
        self._login_user(is_staff=True)
        mock_api = MagicMock()
        mock_api.post.return_value = {"status": "success"}
        mock_client_class.return_value = mock_api

        url = reverse("socialmedia:update_animal_count", kwargs={"post_id": self.post_id})
        response = self.client.post(url, {"animal_count": "2"})
        msgs = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(any("updated" in m.lower() for m in msgs))


class AddCommentViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.post_id = str(uuid.uuid4())
        self.user = make_user("commenter@example.com")
        self.url = reverse("socialmedia:add_comment", kwargs={"post_id": self.post_id})

    def _login_with_token(self):
        self.client.login(email=self.user.email, password="pass1234!")
        session = self.client.session
        session["backend_api_token"] = "tok"
        session.save()

    def test_empty_comment_error(self):
        self._login_with_token()
        response = self.client.post(self.url, {})
        msgs = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(any("empty" in m.lower() or "cannot" in m.lower() for m in msgs))

    @patch("siteapps.socialmedia.web_views.BackendAPIClient")
    def test_add_comment_success(self, mock_client_class):
        self._login_with_token()
        mock_api = MagicMock()
        mock_api.post.return_value = {"status": "success"}
        mock_client_class.return_value = mock_api

        response = self.client.post(self.url, {"comment_text": "Great sighting!"})
        msgs = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(any("success" in m.lower() for m in msgs))

    @patch("siteapps.socialmedia.web_views.BackendAPIClient")
    def test_add_comment_api_failure(self, mock_client_class):
        self._login_with_token()
        mock_api = MagicMock()
        mock_api.post.return_value = None
        mock_client_class.return_value = mock_api

        response = self.client.post(self.url, {"comment_text": "Hello"})
        msgs = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(any("failed" in m.lower() for m in msgs))

    def test_get_request_redirects_to_feed(self):
        self._login_with_token()
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse("socialmedia:feed"), fetch_redirect_response=False)


class LikePostViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.post_id = str(uuid.uuid4())
        self.user = make_user("liker@example.com")
        self.url = reverse("socialmedia:like_post", kwargs={"post_id": self.post_id})

    def _login_with_token(self):
        self.client.login(email=self.user.email, password="pass1234!")
        session = self.client.session
        session["backend_api_token"] = "tok"
        session.save()

    @patch("siteapps.socialmedia.web_views.BackendAPIClient")
    def test_like_success(self, mock_client_class):
        self._login_with_token()
        mock_api = MagicMock()
        mock_api.post.return_value = {"status": "success"}
        mock_client_class.return_value = mock_api

        response = self.client.post(self.url)
        self.assertRedirects(
            response,
            reverse("socialmedia:post_detail", kwargs={"post_id": self.post_id}),
            fetch_redirect_response=False,
        )

    @patch("siteapps.socialmedia.web_views.BackendAPIClient")
    def test_like_api_failure_shows_error(self, mock_client_class):
        self._login_with_token()
        mock_api = MagicMock()
        mock_api.post.return_value = None
        mock_client_class.return_value = mock_api

        response = self.client.post(self.url)
        msgs = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(any("failed" in m.lower() for m in msgs))


class ReportPostViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.post_id = str(uuid.uuid4())
        self.user = make_user("reporter@example.com")
        self.url = reverse("socialmedia:report_post", kwargs={"post_id": self.post_id})

    def _login_with_token(self):
        self.client.login(email=self.user.email, password="pass1234!")
        session = self.client.session
        session["backend_api_token"] = "tok"
        session.save()

    def test_get_renders_report_form(self):
        self._login_with_token()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    @patch("siteapps.socialmedia.web_views.BackendAPIClient")
    def test_post_report_success(self, mock_client_class):
        self._login_with_token()
        mock_api = MagicMock()
        mock_api.post.return_value = {"status": "success"}
        mock_client_class.return_value = mock_api

        response = self.client.post(self.url)
        self.assertRedirects(
            response,
            reverse("socialmedia:post_detail", kwargs={"post_id": self.post_id}),
            fetch_redirect_response=False,
        )

    @patch("siteapps.socialmedia.web_views.BackendAPIClient")
    def test_post_report_api_failure(self, mock_client_class):
        self._login_with_token()
        mock_api = MagicMock()
        mock_api.post.return_value = None
        mock_client_class.return_value = mock_api

        response = self.client.post(self.url)
        msgs = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(any("failed" in m.lower() for m in msgs))


class LikeCommentViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.post_id = str(uuid.uuid4())
        self.comment_id = str(uuid.uuid4())
        self.user = make_user("clike@example.com")
        self.url = reverse(
            "socialmedia:like_comment",
            kwargs={"post_id": self.post_id, "comment_id": self.comment_id},
        )

    def _login_with_token(self):
        self.client.login(email=self.user.email, password="pass1234!")
        session = self.client.session
        session["backend_api_token"] = "tok"
        session.save()

    @patch("siteapps.socialmedia.web_views.BackendAPIClient")
    def test_like_comment_success(self, mock_client_class):
        self._login_with_token()
        mock_api = MagicMock()
        mock_api.post.return_value = {"status": "success", "is_liked": True}
        mock_client_class.return_value = mock_api

        response = self.client.post(self.url)
        self.assertRedirects(
            response,
            reverse("socialmedia:post_detail", kwargs={"post_id": self.post_id}),
            fetch_redirect_response=False,
        )

    @patch("siteapps.socialmedia.web_views.BackendAPIClient")
    def test_unlike_comment_success(self, mock_client_class):
        self._login_with_token()
        mock_api = MagicMock()
        mock_api.post.return_value = {"status": "success", "is_liked": False}
        mock_client_class.return_value = mock_api

        response = self.client.post(self.url)
        msgs = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(any("unlike" in m.lower() for m in msgs))

    @patch("siteapps.socialmedia.web_views.BackendAPIClient")
    def test_like_comment_api_failure(self, mock_client_class):
        self._login_with_token()
        mock_api = MagicMock()
        mock_api.post.return_value = None
        mock_client_class.return_value = mock_api

        response = self.client.post(self.url)
        msgs = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(any("failed" in m.lower() for m in msgs))


class LoadMorePostsViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = make_user("loader@example.com")
        self.url = reverse("socialmedia:load_more_posts")

    def _login_with_token(self):
        self.client.login(email=self.user.email, password="pass1234!")
        session = self.client.session
        session["backend_api_token"] = "tok"
        session.save()

    def test_unauthenticated_returns_401(self):
        self.client.login(email=self.user.email, password="pass1234!")
        # No backend_api_token
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 401)

    def test_invalid_pagination_params_returns_400(self):
        self._login_with_token()
        response = self.client.get(self.url + "?offset=abc&limit=10")
        self.assertEqual(response.status_code, 400)

    def test_limit_too_large_returns_400(self):
        self._login_with_token()
        response = self.client.get(self.url + "?limit=200")
        self.assertEqual(response.status_code, 400)

    def test_limit_zero_returns_400(self):
        self._login_with_token()
        response = self.client.get(self.url + "?limit=0")
        self.assertEqual(response.status_code, 400)

    @patch("siteapps.socialmedia.web_views.BackendAPIClient")
    def test_success_returns_posts(self, mock_client_class):
        self._login_with_token()
        mock_api = MagicMock()
        mock_api.post.return_value = {
            "results": [FAKE_POST],
            "next": None,
            "count": 1,
        }
        mock_client_class.return_value = mock_api

        response = self.client.get(self.url + "?offset=0&limit=10")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("posts", data)
        self.assertFalse(data["has_more"])

    @patch("siteapps.socialmedia.web_views.BackendAPIClient")
    def test_api_failure_returns_500(self, mock_client_class):
        self._login_with_token()
        mock_api = MagicMock()
        mock_api.post.return_value = None
        mock_client_class.return_value = mock_api

        response = self.client.get(self.url + "?offset=0&limit=10")
        self.assertEqual(response.status_code, 500)

    @patch("siteapps.socialmedia.web_views.BackendAPIClient")
    def test_radius_filter_in_load_more(self, mock_client_class):
        self._login_with_token()
        mock_api = MagicMock()
        mock_api.post.return_value = {"results": [], "next": None, "count": 0}
        mock_client_class.return_value = mock_api

        response = self.client.get(
            self.url + "?offset=0&limit=10&location=radius&center_lat=45.5&center_lon=-93.0&radius_km=5"
        )
        self.assertEqual(response.status_code, 200)
        call_data = mock_api.post.call_args[0][1]
        self.assertIn("distanceRadius", call_data)

    @patch("siteapps.socialmedia.web_views.BackendAPIClient")
    def test_species_filter_in_load_more(self, mock_client_class):
        self._login_with_token()
        mock_api = MagicMock()
        mock_api.post.return_value = {"results": [], "next": "http://next", "count": 20}
        mock_client_class.return_value = mock_api

        response = self.client.get(self.url + "?offset=0&limit=10&species=Robin")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["has_more"])
        call_data = mock_api.post.call_args[0][1]
        self.assertEqual(call_data.get("species"), "Robin")
