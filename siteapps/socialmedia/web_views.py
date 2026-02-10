import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from siteapps.users.api_client import BackendAPIClient


logger = logging.getLogger(__name__)


def feed_view(request):
    """Display social media feed"""
    api_token = request.session.get("backend_api_token")
    posts = []
    species_filter = request.GET.get("species")
    location_filter = request.GET.get("location", "global")  # global or local

    # Get posts from backend (requires authentication)
    if api_token:
        api_client = BackendAPIClient(auth_token=api_token)
        data = {}
        if species_filter:
            data["species"] = species_filter
        if location_filter == "local":
            data["distanceRadius"] = 50  # 50km default
            # Would need user's location here

        response = api_client.post("/v1/socialmedia/api/feed/get/", data)
        if response:
            # Backend returns DRF paginated response with 'results' key
            posts = response.get("results", [])
    else:
        # Not authenticated - show empty feed
        posts = []

    # Get species list for filter
    species_list = []
    api_client = BackendAPIClient()
    response = api_client.get("/v1/species/api/names/get/")
    if response and "species_names" in response:
        species_list = response.get("species_names", [])

    context = {
        "posts": posts,
        "species_list": species_list,
        "current_species": species_filter,
        "location_filter": location_filter,
    }
    return render(request, "socialmedia/feed.html", context)


def post_detail_view(request, post_id):
    """Display individual post with comments"""
    api_token = request.session.get("backend_api_token")
    post = None
    comments = []

    if api_token:
        # Fetch from backend - for now, get from feed and find the matching post
        api_client = BackendAPIClient(auth_token=api_token)
        feed_response = api_client.post("/v1/socialmedia/api/feed/get/", {})
        if feed_response and feed_response.get("results"):
            posts = feed_response.get("results", [])
            for p in posts:
                if p.get("id") == str(post_id):
                    post = p
                    break

        # If not found in feed, return error
        if not post:
            messages.error(request, "Post not found.")
            return redirect("socialmedia:feed")

        # Fetch comments for the post
        comments_response = api_client.post(
            "/v1/socialmedia/api/posts/responses/get/auth", {"mediaPostId": str(post_id)}
        )
        if comments_response and comments_response.get("comments"):
            comments = comments_response.get("comments", [])
    else:
        messages.error(request, "Please log in to view posts.")
        return redirect("login")

    context = {
        "post": post,
        "post_id": post_id,
        "comments": comments,
    }
    return render(request, "socialmedia/post_detail.html", context)


@login_required
def add_comment(request, post_id):
    """Add comment to a post"""
    if request.method == "POST":
        comment_text = request.POST.get("comment_text")

        if not comment_text:
            messages.error(request, "Comment cannot be empty.")
            return redirect("socialmedia:post_detail", post_id=post_id)

        api_token = request.session.get("backend_api_token")
        if api_token:
            api_client = BackendAPIClient(auth_token=api_token)
            data = {
                "parentPostId": post_id,
                "commentText": comment_text,
            }
            response = api_client.post("/v1/socialmedia/api/comments/create/", data)

            if response and response.get("status") == "success":
                messages.success(request, "Comment added successfully!")
            else:
                messages.error(request, "Failed to add comment.")

        return redirect("socialmedia:post_detail", post_id=post_id)

    return redirect("socialmedia:feed")


@login_required
def like_post(request, post_id):
    """Like/unlike a post"""
    api_token = request.session.get("backend_api_token")
    if api_token:
        api_client = BackendAPIClient(auth_token=api_token)
        response = api_client.post("/v1/socialmedia/api/posts/like/", {"mediaPostId": post_id})

        if response and response.get("status") == "success":
            messages.success(request, "Post liked!")
        else:
            messages.error(request, "Failed to like post.")

    return redirect("socialmedia:post_detail", post_id=post_id)


@login_required
def report_post(request, post_id):
    """Report inappropriate content"""
    if request.method == "POST":
        reason = request.POST.get("reason")

        api_token = request.session.get("backend_api_token")
        if api_token:
            api_client = BackendAPIClient(auth_token=api_token)
            data = {
                "post_id": post_id,
                "reason": reason,
            }
            response = api_client.post("/v1/socialmedia/api/posts/reports/create", data)

            if response and response.get("status") == "success":
                messages.success(request, "Report submitted. Thank you for helping keep our community safe.")
            else:
                messages.error(request, "Failed to submit report.")

        return redirect("socialmedia:post_detail", post_id=post_id)

    return render(request, "socialmedia/report_post.html", {"post_id": post_id})
