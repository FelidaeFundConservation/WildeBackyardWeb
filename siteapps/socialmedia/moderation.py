import json

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from rest_framework import authentication, permissions, status
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from siteapps.users.models import BannedEmail

from .mixins import createResponse400
from .models import InappropriateContentReport, Media, MediaPost, TextComment


class CreateInappropriateContentReportView(APIView):
    authentication_classes = [authentication.TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = json.loads(request.body)

        content_id = data.get("contentId")
        content_type = data.get("contentType")

        if content_id is None:
            return createResponse400("The ID of the content to report was not provided.")
        if content_type is None:
            return createResponse400("The content type was not provided.")

        report_kwargs = {
            "reported_by": request.user,
            "resolved": False,
        }

        # Get the relevant comment/post object to report
        try:
            if content_type == "TextComment":
                report_kwargs["reported_comment"] = TextComment.objects.get(id=content_id)
                report_kwargs["reported_user"] = report_kwargs["reported_comment"].created_by
            elif content_type == "MediaPost":
                report_kwargs["reported_post"] = MediaPost.objects.get(id=content_id)
                report_kwargs["reported_user"] = report_kwargs["reported_post"].created_by
            else:
                createResponse400("Invalid content type provided (must be either 'TextComment' or 'MediaPost.'")
        except ObjectDoesNotExist:
            return Response(
                status=status.HTTP_404_NOT_FOUND, data={"error": f"Post or comment with id {content_id} wasn't found."}
            )

        # Create the report object if it doesn't exist
        InappropriateContentReport.objects.get_or_create(**report_kwargs)

        return Response(
            status=status.HTTP_201_CREATED,
        )


# Get info for a reported media/comment for admin to view
class GetNextReportedContentView(APIView):
    authentication_classes = [authentication.TokenAuthentication]
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        DELETED_USER = "Deleted User"
        NAME_FIELD = "name"

        # Look for next report to review
        report = InappropriateContentReport.objects.filter(resolved=False)

        if report.exists():
            report_obj = report.first()

            # Reported content is a comment
            if report_obj.reported_comment:
                return Response(
                    status=status.HTTP_200_OK,
                    data={
                        "report_id": report_obj.id,
                        "content_id": report_obj.reported_comment.id,
                        "user_name": getattr(report_obj.reported_comment.created_by, NAME_FIELD, DELETED_USER),
                        "text_content": TextComment.objects.get(id=report_obj.reported_comment.id).text_content,
                    },
                )
            # Reported content is a media post
            elif report_obj.reported_post:
                return Response(
                    status=status.HTTP_200_OK,
                    data={
                        "report_id": report_obj.id,
                        "content_id": report_obj.reported_post.id,
                        "user_name": getattr(report_obj.reported_post.created_by, NAME_FIELD, DELETED_USER),
                        "media": getattr(report_obj.reported_post.media, "file_cloud_path", None),
                        "title": report_obj.reported_post.title,
                        "text_content": report_obj.reported_post.text_content,
                    },
                )
            else:
                return Response(
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        return Response(
            status=status.HTTP_404_NOT_FOUND,
        )


# Resolve reported content by clearing (i.e. nothing wrong with content)
class ClearReportView(APIView):
    authentication_classes = [authentication.TokenAuthentication]
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request):
        data = json.loads(request.body)

        report_id = data.get("reportId")

        if report_id is None:
            return createResponse400("The report ID to clear was not provided.")

        # Get the specified report to clear
        try:
            report_obj = InappropriateContentReport.objects.get(id=report_id)
        except ObjectDoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND, data={"error": f"Report with id {report_id} not found."})

        report_obj.resolved = True
        report_obj.save()

        return Response(
            status=status.HTTP_200_OK,
        )


# For minor conduct (ex: rudeness), remove only the offending post and issue a warning
class IssueWarningView(APIView):
    authentication_classes = [authentication.TokenAuthentication]
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request):
        data = json.loads(request.body)

        report_id = data.get("reportId")
        warning_notes = data.get("warningNotes")

        if report_id is None:
            return createResponse400("The report ID to determine who to warn was not provided.")
        if warning_notes is None:
            return createResponse400("The warning reason was not provided.")

        # Get the specified report to clear
        try:
            report_obj = InappropriateContentReport.objects.get(id=report_id)
        except ObjectDoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND, data={"error": f"Report with id {report_id} not found."})

        user_to_warn = None

        # Delete the offending post or comment
        if report_obj.reported_comment is not None:
            user_to_warn = report_obj.reported_comment.created_by
            report_obj.reported_comment.delete()
            report_obj.reported_comment = None
        if report_obj.reported_post is not None:
            user_to_warn = report_obj.reported_post.created_by
            report_obj.reported_post.delete()
            report_obj.reported_post = None
        # Increment the user's warn count
        if user_to_warn:
            user_to_warn.warnings += 1
            user_to_warn.save()

        # Resolve the report
        report_obj.warning_notes = warning_notes
        report_obj.resolved = True
        report_obj.save()

        return Response(
            status=status.HTTP_200_OK,
        )


# For major conduct (ex: bad profanity, explicit, etc) or multiple warnings, ban user from posting and remove all content related to them
class BanUserView(APIView):
    authentication_classes = [authentication.TokenAuthentication]
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request):
        data = json.loads(request.body)

        report_id = data.get("reportId")
        ban_reason = data.get("banReason")

        if report_id is None:
            return createResponse400("The report ID to determine who to ban was not provided.")
        if ban_reason is None:
            return createResponse400("The ban reason was not provided.")

        # Get the specified report to clear
        try:
            report_obj = InappropriateContentReport.objects.get(id=report_id)
        except ObjectDoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND, data={"error": f"Report with id {report_id} not found."})

        user_to_ban = None

        # Get user to ban
        if report_obj.reported_comment is not None:
            user_to_ban = report_obj.reported_comment.created_by
        if report_obj.reported_post is not None:
            user_to_ban = report_obj.reported_post.created_by

        # Delete all content related to user
        if user_to_ban:
            MediaPost.objects.filter(created_by=user_to_ban).delete()
            TextComment.objects.filter(created_by=user_to_ban).delete()
            report_obj.reported_post = None
            report_obj.reported_comment = None
            # Add email to banned list to avoid account recreation bypass
            BannedEmail.objects.create(email=user_to_ban.email, ban_reason=ban_reason)

        # Resolve the report
        report_obj.resolved = True
        report_obj.save()

        return Response(
            status=status.HTTP_200_OK,
        )
