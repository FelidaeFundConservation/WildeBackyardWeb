# Licensed under the MIT License.
# See LICENSE file in the project root for full license information.

from django.urls import path, re_path

# Moderation views disabled until BannedEmail model is created
# from siteapps.socialmedia.moderation import (
#     BanUserView,
#     ClearReportView,
#     CreateInappropriateContentReportView,
#     GetNextReportedContentView,
#     IssueWarningView,
# )
from siteapps.socialmedia.views import (
    CreateCommentView,
    CreatePostView,
    EditPostView,
    GetPostResponsesAuthenticatedView,
    GetPostResponsesNoAuthView,
    GetRecentPostsView,
    LikeCommentView,
    LikePostView,
)
from siteapps.socialmedia.web_views import (
    add_comment,
    feed_view,
    like_comment,
    like_post,
    load_more_posts,
    post_detail_view,
    report_post,
    update_animal_count,
    update_description,
    update_details,
    update_location,
    update_post_title,
    update_sighting_species,
    vote_quality_metric,
)

app_name = "socialmedia"

urlpatterns = [
    # Web views
    path("", feed_view, name="feed"),
    path("load-more/", load_more_posts, name="load_more_posts"),
    path("post/<uuid:post_id>/", post_detail_view, name="post_detail"),
    path("post/<uuid:post_id>/comment/", add_comment, name="add_comment"),
    path("post/<uuid:post_id>/like/", like_post, name="like_post"),
    path("post/<uuid:post_id>/comment/<uuid:comment_id>/like/", like_comment, name="like_comment"),
    path("post/<uuid:post_id>/report/", report_post, name="report_post"),
    path("post/<uuid:post_id>/quality/<str:metric>/", vote_quality_metric, name="vote_quality_metric"),
    path("post/<uuid:post_id>/species/", update_sighting_species, name="update_sighting_species"),
    path("post/<uuid:post_id>/animal-count/", update_animal_count, name="update_animal_count"),
    path("post/<uuid:post_id>/description/", update_description, name="update_description"),
    path("post/<uuid:post_id>/title/", update_post_title, name="update_post_title"),
    path("post/<uuid:post_id>/details/", update_details, name="update_details"),
    path("post/<uuid:post_id>/location/", update_location, name="update_location"),
    # API views
    path("api/comments/create/", CreateCommentView.as_view(), name="create_comment"),
    path("api/comments/like/", LikeCommentView.as_view(), name="like_comment"),
    path("api/posts/create/", CreatePostView.as_view(), name="create_post"),
    path("api/posts/edit/", EditPostView.as_view(), name="edit_post"),
    path("api/posts/like/", LikePostView.as_view(), name="like_post"),
    re_path(r"^api/feed/get/$", GetRecentPostsView.as_view(), name="get_posts"),
    path("api/posts/responses/get/noauth", GetPostResponsesNoAuthView.as_view(), name="get_post_responses_noauth"),
    path("api/posts/responses/get/auth", GetPostResponsesAuthenticatedView.as_view(), name="get_post_responses_auth"),
    # Moderation API endpoints disabled until BannedEmail model is created
    # path("api/posts/reports/create", CreateInappropriateContentReportView.as_view(), name="report_content"),
    # path("api/posts/reports/review", GetNextReportedContentView.as_view(), name="get_reported_content"),
    # path("api/posts/reports/clear", ClearReportView.as_view(), name="clear_report"),
    # path("api/posts/reports/warn", IssueWarningView.as_view(), name="issue_warning"),
    # path("api/posts/reports/ban", BanUserView.as_view(), name="ban_user"),
]
