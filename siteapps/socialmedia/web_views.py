import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render

from siteapps.users.api_client import BackendAPIClient

logger = logging.getLogger(__name__)

# Pagination constants
MAX_POSTS_PER_REQUEST = 100


def _normalize_post(post):
    """Map API field names to the field names expected by feed/sightings templates."""
    media = post.get("media") or {}
    post["media_url"] = media.get("url")
    post["is_video"] = media.get("is_video", False)
    post["user_name"] = post.get("created_by")
    post["created"] = post.get("encounter_datetime")
    additional = post.get("additional_info") or {}
    post["camera_model"] = additional.get("camera_model")
    post["habitat_type"] = additional.get("habitat_type")
    return post


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

        # Build URL with query parameters for pagination
        endpoint = "/v1/socialmedia/api/feed/get/?limit=10&offset=0"
        response = api_client.post(endpoint, data)
        if response:
            # Backend returns DRF paginated response with 'results' key
            posts = [_normalize_post(p) for p in response.get("results", [])]
    else:
        # Not authenticated - show empty feed
        posts = []

    # Get species list for filter (no auth required)
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

    if not api_token:
        messages.error(request, "Please log in to view posts.")
        return redirect("users:login")

    api_client = BackendAPIClient(auth_token=api_token)

    # Fetch post from the backend API (single source of truth regardless of which
    # database instance the web app is connected to).
    post_response = api_client.get(f"/v1/socialmedia/api/posts/{post_id}/")
    if post_response is None:
        messages.error(request, "Post not found or could not be loaded.")
        return redirect("socialmedia:feed")

    post = _normalize_post(post_response)

    # Fetch comments and like status from the backend
    comments_response = api_client.post("/v1/socialmedia/api/posts/responses/get/auth", {"mediaPostId": str(post_id)})
    if comments_response:
        comments = comments_response.get("comments", [])
        post["user_has_liked"] = comments_response.get("liked_by_current_user", False)
        post["likes_count"] = comments_response.get("like_count", 0)

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
                "parentPostId": str(post_id),
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
        response = api_client.post("/v1/socialmedia/api/posts/like/", {"mediaPostId": str(post_id)})

        if response and response.get("status") == "success":
            messages.success(request, "Post liked!")
        else:
            messages.error(request, "Failed to like post.")

    return redirect("socialmedia:post_detail", post_id=post_id)


@login_required
def report_post(request, post_id):
    """Report inappropriate content"""
    if request.method == "POST":
        api_token = request.session.get("backend_api_token")
        if api_token:
            api_client = BackendAPIClient(auth_token=api_token)
            data = {
                "contentId": int(post_id),
                "contentType": "MediaPost",
            }
            response = api_client.post("/v1/socialmedia/api/posts/reports/create", data)

            if response and response.get("status") == "success":
                messages.success(request, "Report submitted. Thank you for helping keep our community safe.")
            else:
                messages.error(request, "Failed to submit report.")

        return redirect("socialmedia:post_detail", post_id=post_id)

    return render(request, "socialmedia/report_post.html", {"post_id": post_id})


@login_required
def like_comment(request, post_id, comment_id):
    """Like/unlike a comment"""
    api_token = request.session.get("backend_api_token")
    if api_token:
        api_client = BackendAPIClient(auth_token=api_token)
        response = api_client.post("/v1/socialmedia/api/comments/like/", {"commentId": str(comment_id)})

        if response and response.get("status") == "success":
            # Show appropriate message based on the action
            is_liked = response.get("is_liked", True)
            if is_liked:
                messages.success(request, "Comment liked!")
            else:
                messages.success(request, "Comment unliked!")
        else:
            messages.error(request, "Failed to update comment.")

    return redirect("socialmedia:post_detail", post_id=post_id)


def load_more_posts(request):
    """AJAX endpoint to load more posts for infinite scroll"""
    api_token = request.session.get("backend_api_token")

    if not api_token:
        return JsonResponse({"error": "Authentication required"}, status=401)

    # Get and validate pagination parameters
    try:
        offset = int(request.GET.get("offset", 0))
        limit = int(request.GET.get("limit", 10))
    except ValueError:
        return JsonResponse({"error": "Invalid pagination parameters"}, status=400)

    # Validate limit to prevent abuse
    if limit < 1 or limit > MAX_POSTS_PER_REQUEST:
        return JsonResponse({"error": f"Limit must be between 1 and {MAX_POSTS_PER_REQUEST}"}, status=400)

    # Get filter parameters
    species_filter = request.GET.get("species")
    # TODO: implement local filtering - requires user location
    # location_filter = request.GET.get("location", "global")

    # Build API request data
    api_client = BackendAPIClient(auth_token=api_token)
    data = {}

    if species_filter:
        data["species"] = species_filter

    endpoint = f"/v1/socialmedia/api/feed/get/?offset={offset}&limit={limit}"

    # Fetch posts from backend
    response = api_client.post(endpoint, data)

    if not response:
        return JsonResponse({"error": "Failed to fetch posts"}, status=500)

    # Backend returns paginated response with 'results', 'next', 'count' keys
    posts = response.get("results", [])
    next_url = response.get("next")
    total_count = response.get("count", 0)

    # Format posts data for frontend
    posts_data = []
    for post in posts:
        media_url = None
        is_video = False
        if post.get("media"):
            media_url = post["media"].get("url")
            is_video = post["media"].get("is_video", False)

        post_data = {
            "id": post.get("id"),
            "title": post.get("title"),
            "body": post.get("body"),
            "species": post.get("species"),
            "media_url": media_url,
            "is_video": is_video,
            "user_name": post.get("created_by"),
            "created": post.get("encounter_datetime"),
            "geocoded_location": post.get("geocoded_location"),
            "likes_count": post.get("likes_count", 0),
            "comments_count": post.get("comments_count", 0),
        }
        posts_data.append(post_data)

    return JsonResponse(
        {
            "posts": posts_data,
            "has_more": next_url is not None,
            "total_count": total_count,
        }
    )
