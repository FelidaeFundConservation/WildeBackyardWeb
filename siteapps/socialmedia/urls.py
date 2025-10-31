from django.urls import path, re_path

from siteapps.socialmedia.moderation import (
    BanUserView,
    ClearReportView,
    CreateInappropriateContentReportView,
    GetNextReportedContentView,
    IssueWarningView,
)
from siteapps.socialmedia.views import (
    CreateCommentView,
    CreatePostView,
    EditPostView,
    GetPostResponsesAuthenticatedView,
    GetPostResponsesNoAuthView,
    GetRecentPostsView,
    LikePostView,
)

urlpatterns = [
    path("api/comments/create/", CreateCommentView.as_view(), name="create_comment"),
    path("api/posts/create/", CreatePostView.as_view(), name="create_post"),
    path("api/posts/edit/", EditPostView.as_view(), name="edit_post"),
    path("api/posts/like/", LikePostView.as_view(), name="like_post"),
    re_path(r"^api/feed/get/$", GetRecentPostsView.as_view(), name="get_posts"),
    path("api/posts/responses/get/noauth", GetPostResponsesNoAuthView.as_view(), name="get_post_responses_noauth"),
    path("api/posts/responses/get/auth", GetPostResponsesAuthenticatedView.as_view(), name="get_post_responses_auth"),
    path("api/posts/reports/create", CreateInappropriateContentReportView.as_view(), name="report_content"),
    path("api/posts/reports/review", GetNextReportedContentView.as_view(), name="get_reported_content"),
    path("api/posts/reports/clear", ClearReportView.as_view(), name="clear_report"),
    path("api/posts/reports/warn", IssueWarningView.as_view(), name="issue_warning"),
    path("api/posts/reports/ban", BanUserView.as_view(), name="ban_user"),
]
