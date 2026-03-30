"""Tests for siteapps/socialmedia/moderation.py"""

import json
import uuid
from datetime import datetime, timezone

from django.test import TestCase
from rest_framework.authtoken.models import Token
from rest_framework.test import APIRequestFactory, force_authenticate

from siteapps.socialmedia.models import InappropriateContentReport, MediaPost, TextComment
from siteapps.socialmedia.moderation import (
    BanUserView,
    ClearReportView,
    CreateInappropriateContentReportView,
    GetNextReportedContentView,
    IssueWarningView,
)
from siteapps.species.models import SpeciesName
from siteapps.users.models import BannedEmail, User


def make_user(email, is_staff=False, is_superuser=False):
    user = User.objects.create_user(email=email, password="pass1234!", name=f"User {email}")
    user.is_staff = is_staff
    user.is_superuser = is_superuser
    user.save()
    return user


def make_post(created_by):
    species, _ = SpeciesName.objects.get_or_create(name="Robin", scientific_name="Turdus migratorius")
    return MediaPost.objects.create(
        created_by=created_by,
        title="Test Post",
        encounter_datetime=datetime(2024, 1, 1, tzinfo=timezone.utc),
        geoprivacy="public",
        public_location_latitude=45.0,
        public_location_longitude=-93.0,
        species=species,
    )


def make_comment(created_by, post=None):
    return TextComment.objects.create(created_by=created_by, text_content="Offensive comment")


def make_report(reported_by, reported_user, post=None, comment=None):
    kwargs = {
        "reported_by": reported_by,
        "reported_user": reported_user,
        "resolved": False,
    }
    if post:
        kwargs["reported_post"] = post
    if comment:
        kwargs["reported_comment"] = comment
    return InappropriateContentReport.objects.create(**kwargs)


class CreateReportViewTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.reporter = make_user("reporter@example.com")
        self.offender = make_user("offender@example.com")
        self.token, _ = Token.objects.get_or_create(user=self.reporter)
        self.post = make_post(self.offender)
        self.comment = make_comment(self.offender)

    def _call(self, data, user=None):
        request = self.factory.post(
            "/feed/api/posts/reports/create",
            data=json.dumps(data),
            content_type="application/json",
        )
        force_authenticate(request, user=user or self.reporter, token=self.token)
        return CreateInappropriateContentReportView.as_view()(request)

    def test_report_media_post_success(self):
        response = self._call({"contentId": str(self.post.id), "contentType": "MediaPost"})
        self.assertEqual(response.status_code, 201)
        self.assertTrue(InappropriateContentReport.objects.filter(reported_post=self.post).exists())

    def test_report_text_comment_success(self):
        response = self._call({"contentId": str(self.comment.id), "contentType": "TextComment"})
        self.assertEqual(response.status_code, 201)
        self.assertTrue(InappropriateContentReport.objects.filter(reported_comment=self.comment).exists())

    def test_missing_content_id(self):
        response = self._call({"contentType": "MediaPost"})
        self.assertEqual(response.status_code, 400)

    def test_missing_content_type(self):
        response = self._call({"contentId": str(self.post.id)})
        self.assertEqual(response.status_code, 400)

    def test_invalid_content_id(self):
        response = self._call({"contentId": str(uuid.uuid4()), "contentType": "MediaPost"})
        self.assertEqual(response.status_code, 404)

    def test_unauthenticated_denied(self):
        request = self.factory.post(
            "/feed/api/posts/reports/create",
            data=json.dumps({"contentId": str(self.post.id), "contentType": "MediaPost"}),
            content_type="application/json",
        )
        response = CreateInappropriateContentReportView.as_view()(request)
        self.assertEqual(response.status_code, 401)

    def test_duplicate_report_idempotent(self):
        self._call({"contentId": str(self.post.id), "contentType": "MediaPost"})
        response = self._call({"contentId": str(self.post.id), "contentType": "MediaPost"})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(InappropriateContentReport.objects.filter(reported_post=self.post).count(), 1)


class GetNextReportedContentViewTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.admin = make_user("admin@example.com", is_staff=True)
        self.regular = make_user("regular@example.com")
        self.admin_token, _ = Token.objects.get_or_create(user=self.admin)
        self.offender = make_user("offender@example.com")

    def _call(self, user, token):
        request = self.factory.get("/feed/api/posts/reports/review")
        force_authenticate(request, user=user, token=token)
        return GetNextReportedContentView.as_view()(request)

    def test_no_reports_returns_404(self):
        response = self._call(self.admin, self.admin_token)
        self.assertEqual(response.status_code, 404)

    def test_non_staff_denied(self):
        token, _ = Token.objects.get_or_create(user=self.regular)
        response = self._call(self.regular, token)
        self.assertEqual(response.status_code, 403)

    def test_returns_post_report(self):
        post = make_post(self.offender)
        make_report(self.admin, self.offender, post=post)
        response = self._call(self.admin, self.admin_token)
        self.assertEqual(response.status_code, 200)
        self.assertIn("report_id", response.data)
        self.assertIn("content_id", response.data)

    def test_returns_comment_report(self):
        comment = make_comment(self.offender)
        make_report(self.admin, self.offender, comment=comment)
        response = self._call(self.admin, self.admin_token)
        self.assertEqual(response.status_code, 200)
        self.assertIn("text_content", response.data)

    def test_skips_resolved_reports(self):
        post = make_post(self.offender)
        report = make_report(self.admin, self.offender, post=post)
        report.resolved = True
        report.save()
        response = self._call(self.admin, self.admin_token)
        self.assertEqual(response.status_code, 404)


class ClearReportViewTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.admin = make_user("admin2@example.com", is_staff=True)
        self.admin_token, _ = Token.objects.get_or_create(user=self.admin)
        self.offender = make_user("offender2@example.com")

    def _call(self, data, user=None, token=None):
        request = self.factory.post(
            "/feed/api/posts/reports/clear",
            data=json.dumps(data),
            content_type="application/json",
        )
        force_authenticate(request, user=user or self.admin, token=token or self.admin_token)
        return ClearReportView.as_view()(request)

    def test_clear_report_success(self):
        post = make_post(self.offender)
        report = make_report(self.admin, self.offender, post=post)
        response = self._call({"reportId": str(report.id)})
        self.assertEqual(response.status_code, 200)
        report.refresh_from_db()
        self.assertTrue(report.resolved)

    def test_missing_report_id(self):
        response = self._call({})
        self.assertEqual(response.status_code, 400)

    def test_nonexistent_report_id(self):
        response = self._call({"reportId": str(uuid.uuid4())})
        self.assertEqual(response.status_code, 404)

    def test_non_staff_denied(self):
        regular = make_user("regular2@example.com")
        token, _ = Token.objects.get_or_create(user=regular)
        post = make_post(self.offender)
        report = make_report(self.admin, self.offender, post=post)
        response = self._call({"reportId": str(report.id)}, user=regular, token=token)
        self.assertEqual(response.status_code, 403)


class IssueWarningViewTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.admin = make_user("warnAdmin@example.com", is_staff=True)
        self.admin_token, _ = Token.objects.get_or_create(user=self.admin)
        self.offender = make_user("warnOffender@example.com")

    def _call(self, data, user=None, token=None):
        request = self.factory.post(
            "/feed/api/posts/reports/warn",
            data=json.dumps(data),
            content_type="application/json",
        )
        force_authenticate(request, user=user or self.admin, token=token or self.admin_token)
        return IssueWarningView.as_view()(request)

    def test_warn_for_post_success(self):
        post = make_post(self.offender)
        report = make_report(self.admin, self.offender, post=post)
        initial_warnings = self.offender.warnings
        response = self._call({"reportId": str(report.id), "warningNotes": "Bad post"})
        self.assertEqual(response.status_code, 200)
        self.offender.refresh_from_db()
        self.assertEqual(self.offender.warnings, initial_warnings + 1)
        self.assertFalse(MediaPost.objects.filter(id=post.id).exists())
        report.refresh_from_db()
        self.assertTrue(report.resolved)

    def test_warn_for_comment_success(self):
        comment = make_comment(self.offender)
        report = make_report(self.admin, self.offender, comment=comment)
        initial_warnings = self.offender.warnings
        response = self._call({"reportId": str(report.id), "warningNotes": "Rude comment"})
        self.assertEqual(response.status_code, 200)
        self.offender.refresh_from_db()
        self.assertEqual(self.offender.warnings, initial_warnings + 1)
        self.assertFalse(TextComment.objects.filter(id=comment.id).exists())

    def test_missing_report_id(self):
        response = self._call({"warningNotes": "Note"})
        self.assertEqual(response.status_code, 400)

    def test_missing_warning_notes(self):
        post = make_post(self.offender)
        report = make_report(self.admin, self.offender, post=post)
        response = self._call({"reportId": str(report.id)})
        self.assertEqual(response.status_code, 400)

    def test_nonexistent_report_id(self):
        response = self._call({"reportId": str(uuid.uuid4()), "warningNotes": "Note"})
        self.assertEqual(response.status_code, 404)

    def test_non_staff_denied(self):
        regular = make_user("regularWarn@example.com")
        token, _ = Token.objects.get_or_create(user=regular)
        post = make_post(self.offender)
        report = make_report(self.admin, self.offender, post=post)
        response = self._call({"reportId": str(report.id), "warningNotes": "Note"}, user=regular, token=token)
        self.assertEqual(response.status_code, 403)


class BanUserViewTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.admin = make_user("banAdmin@example.com", is_staff=True)
        self.admin_token, _ = Token.objects.get_or_create(user=self.admin)
        self.offender = make_user("banOffender@example.com")

    def _call(self, data, user=None, token=None):
        request = self.factory.post(
            "/feed/api/posts/reports/ban",
            data=json.dumps(data),
            content_type="application/json",
        )
        force_authenticate(request, user=user or self.admin, token=token or self.admin_token)
        return BanUserView.as_view()(request)

    def test_ban_for_post_success(self):
        post = make_post(self.offender)
        report = make_report(self.admin, self.offender, post=post)
        response = self._call({"reportId": str(report.id), "banReason": "Explicit content"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(MediaPost.objects.filter(created_by=self.offender).exists())
        self.assertTrue(BannedEmail.objects.filter(email=self.offender.email).exists())
        report.refresh_from_db()
        self.assertTrue(report.resolved)

    def test_ban_for_comment_success(self):
        comment = make_comment(self.offender)
        report = make_report(self.admin, self.offender, comment=comment)
        response = self._call({"reportId": str(report.id), "banReason": "Harassment"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(TextComment.objects.filter(created_by=self.offender).exists())
        self.assertTrue(BannedEmail.objects.filter(email=self.offender.email).exists())

    def test_missing_report_id(self):
        response = self._call({"banReason": "Bad"})
        self.assertEqual(response.status_code, 400)

    def test_missing_ban_reason(self):
        post = make_post(self.offender)
        report = make_report(self.admin, self.offender, post=post)
        response = self._call({"reportId": str(report.id)})
        self.assertEqual(response.status_code, 400)

    def test_nonexistent_report(self):
        response = self._call({"reportId": str(uuid.uuid4()), "banReason": "Bad"})
        self.assertEqual(response.status_code, 404)

    def test_non_staff_denied(self):
        regular = make_user("regularBan@example.com")
        token, _ = Token.objects.get_or_create(user=regular)
        post = make_post(self.offender)
        report = make_report(self.admin, self.offender, post=post)
        response = self._call({"reportId": str(report.id), "banReason": "Bad"}, user=regular, token=token)
        self.assertEqual(response.status_code, 403)
