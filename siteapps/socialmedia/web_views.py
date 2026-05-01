import json
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render

from siteapps.sightings.models import BulkUploadSighting
from siteapps.users.api_client import BackendAPIClient

logger = logging.getLogger(__name__)

# Pagination constants
MAX_POSTS_PER_REQUEST = 100


def _parse_radius_params(request):
    """Parse and validate center lat/lon and radius_km from request GET params.

    Returns a tuple (center_lat, center_lon, radius_km) where each value is a
    float or None if missing / invalid.
    """
    try:
        center_lat = float(request.GET.get("center_lat")) if request.GET.get("center_lat") else None
        center_lon = float(request.GET.get("center_lon")) if request.GET.get("center_lon") else None
        radius_km = float(request.GET.get("radius_km")) if request.GET.get("radius_km") else None
    except (ValueError, TypeError):
        return None, None, None
    return center_lat, center_lon, radius_km


def _normalize_post(post):
    """Map API field names to the field names expected by feed/sightings templates."""
    media = post.get("media") or {}
    post["media_url"] = media.get("url")
    post["is_video"] = media.get("is_video", False)
    post["user_name"] = post.get("created_by")
    post["created"] = post.get("encounter_datetime")
    additional = post.get("additional_info") or {}
    post["camera_model"] = additional.get("camera_model")
    post["iucn_habitat_lvl1"] = additional.get("iucn_habitat_lvl1_name")
    post["iucn_habitat_lvl1_code"] = additional.get("iucn_habitat_lvl1_code")
    post["iucn_habitat_lvl2"] = additional.get("iucn_habitat_lvl2_name")
    post["iucn_habitat_lvl2_code"] = additional.get("iucn_habitat_lvl2_code")

    # Parse timestamp offset JSON if present
    timestamp_offset_json = additional.get("camera_timestamp_offset_error_details")
    if timestamp_offset_json:
        try:
            timestamp_data = json.loads(timestamp_offset_json)
            post["incorrect_date"] = timestamp_data.get("incorrectDate", "")
            post["correct_date"] = timestamp_data.get("correctDate", "")
            post["incorrect_time"] = timestamp_data.get("incorrectTime", "")
            post["correct_time"] = timestamp_data.get("correctTime", "")
        except (json.JSONDecodeError, TypeError):
            # If JSON parsing fails, leave fields empty
            post["incorrect_date"] = ""
            post["correct_date"] = ""
            post["incorrect_time"] = ""
            post["correct_time"] = ""
    else:
        post["incorrect_date"] = ""
        post["correct_date"] = ""
        post["incorrect_time"] = ""
        post["correct_time"] = ""

    # license dict passed through as-is; templates access post.license.code, .label, etc.
    return post


def feed_view(request):
    """Display social media feed"""
    api_token = request.session.get("backend_api_token")
    posts = []
    species_filter = request.GET.get("species")
    location_filter = request.GET.get("location", "global")  # global, radius, zipcode, or place
    user_filter = request.GET.get("user_filter", "all")  # all, self, or other
    user_display_name_filter = request.GET.get("user_display_name", "").strip()
    verification_filter = request.GET.get("verification_filter", "all")  # all, verified, unverified

    # Custom radius filter parameters
    center_lat, center_lon, radius_km = _parse_radius_params(request)

    # ZIP code boundary filter parameters
    zip_code_boundary = request.GET.get("zip_code_boundary", "").strip()
    zip_code_country = request.GET.get("zip_code_country", "US").upper()

    # Place name filter parameters
    place_name = request.GET.get("place_name", "").strip()
    place_country = request.GET.get("place_country", "US").upper()
    place_radius = request.GET.get("place_radius", "10").strip()
    try:
        place_radius = float(place_radius) if place_radius else 10.0
    except ValueError:
        place_radius = 10.0

    # If the user is authenticated but has no backend API token, their session
    # was created via a local-only auth path (e.g. ModelBackend). Redirect them
    # to login so the BackendAPIAuthBackend can run and store the token.
    if request.user.is_authenticated and not api_token:
        messages.info(request, "Please log in again to load your feed.")
        return redirect("users:login")

    # Get posts from backend (requires authentication)
    if api_token:
        api_client = BackendAPIClient(auth_token=api_token)
        data = {}
        if species_filter:
            data["species"] = species_filter
        if (
            location_filter == "radius"
            and center_lat is not None
            and center_lon is not None
            and radius_km is not None
            and radius_km > 0
        ):
            data["distanceRadius"] = radius_km
            data["userLatitude"] = center_lat
            data["userLongitude"] = center_lon

        # ZIP code boundary filter
        if location_filter == "zipcode" and zip_code_boundary:
            data["zipCodeBoundary"] = zip_code_boundary
            data["zipCodeCountry"] = zip_code_country

        # Place name filter
        elif location_filter == "place" and place_name:
            data["placeName"] = place_name
            data["placeCountry"] = place_country
            data["placeRadius"] = place_radius

        # User filter: "self" = current user's backend UUID, "other" = display name search
        if user_filter == "self":
            backend_user_id = request.session.get("backend_user_id")
            if backend_user_id:
                data["userId"] = backend_user_id
        elif user_filter == "other" and user_display_name_filter:
            data["userDisplayName"] = user_display_name_filter

        if verification_filter in ("verified", "unverified"):
            data["verificationFilter"] = verification_filter

        # Build URL with query parameters for pagination
        endpoint = "/v1/socialmedia/api/feed/get/?limit=10&offset=0"
        response = api_client.post(endpoint, data)
        if response:
            # Backend returns DRF paginated response with 'results' key
            posts = [_normalize_post(p) for p in response.get("results", [])]
    else:
        # Not authenticated - show empty feed
        posts = []

    context = {
        "posts": posts,
        "current_species": species_filter,
        "location_filter": location_filter,
        "center_lat": center_lat,
        "center_lon": center_lon,
        "radius_km": radius_km,
        "zip_code_boundary": zip_code_boundary,
        "zip_code_country": zip_code_country,
        "place_name": place_name,
        "place_country": place_country,
        "place_radius": place_radius,
        "user_filter": user_filter,
        "user_display_name_filter": user_display_name_filter,
        "verification_filter": verification_filter,
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
    quality_metrics = post_response.get("quality_metrics", [])

    # Build zipped (common_name, taxon_or_None) pairs for template rendering
    species_list = post.get("species_list") or []
    taxa_list = post.get("taxa_list") or [None] * len(species_list)
    post["species_pairs"] = list(zip(species_list, taxa_list))

    # Fetch comments and like status from the backend
    comments_response = api_client.post("/v1/socialmedia/api/posts/responses/get/auth", {"mediaPostId": str(post_id)})
    if comments_response:
        comments = comments_response.get("comments", [])
        post["user_has_liked"] = comments_response.get("liked_by_current_user", False)
        post["likes_count"] = comments_response.get("like_count", 0)

    # Support a ?back= param so callers (e.g. bulk upload detail) can override the back URL.
    back_url = request.GET.get("back", "")
    # Only allow relative paths to prevent open-redirect.
    if not back_url.startswith("/") or back_url.startswith("//"):
        back_url = ""

    context = {
        "post": post,
        "post_id": post_id,
        "comments": comments,
        "quality_metrics": quality_metrics,
        "back_url": back_url,
    }
    return render(request, "socialmedia/post_detail.html", context)


@login_required
def vote_quality_metric(request, post_id, metric):
    """Submit or toggle a quality-metric vote. Restricted to staff and superusers."""
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, "You do not have permission to vote on quality metrics.")
        return redirect("socialmedia:post_detail", post_id=post_id)

    if request.method == "POST":
        agree_str = request.POST.get("agree", "").lower()
        agree = agree_str == "true"

        api_token = request.session.get("backend_api_token")
        if api_token:
            api_client = BackendAPIClient(auth_token=api_token)
            response = api_client.post(
                f"/v1/socialmedia/api/posts/{post_id}/quality/{metric}/",
                {"agree": agree},
            )
            if response is None:
                messages.error(request, "Failed to record quality vote.")

    return redirect("socialmedia:post_detail", post_id=post_id)


@login_required
def update_sighting_species(request, post_id):
    """Replace the species list for a post. Restricted to staff and superusers."""
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, "You do not have permission to edit species.")
        return redirect("socialmedia:post_detail", post_id=post_id)

    if request.method == "POST":
        species_names = request.POST.getlist("species_list")
        species_names = [s for s in species_names if s.strip()]

        if not species_names:
            messages.error(request, "At least one species is required.")
            return redirect("socialmedia:post_detail", post_id=post_id)

        api_token = request.session.get("backend_api_token")
        if api_token:
            api_client = BackendAPIClient(auth_token=api_token)
            is_bulk_upload = BulkUploadSighting.objects.filter(backend_post_id=post_id).exists()
            payload = {"species_list": species_names}
            if is_bulk_upload:
                payload["update_title"] = True
            response = api_client.post(
                f"/v1/socialmedia/api/posts/{post_id}/species/",
                payload,
            )
            if response is None:
                messages.error(request, "Failed to update species list.")
            else:
                messages.success(request, "Species list updated.")

    return redirect("socialmedia:post_detail", post_id=post_id)


@login_required
def update_animal_count(request, post_id):
    """Update the animal count for a post. Restricted to staff and superusers."""
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, "You do not have permission to edit animal count.")
        return redirect("socialmedia:post_detail", post_id=post_id)

    if request.method == "POST":
        animal_count = request.POST.get("animal_count", "").strip()
        if not animal_count:
            messages.error(request, "Animal count is required.")
            return redirect("socialmedia:post_detail", post_id=post_id)

        api_token = request.session.get("backend_api_token")
        if api_token:
            api_client = BackendAPIClient(auth_token=api_token)
            response = api_client.post(
                f"/v1/socialmedia/api/posts/{post_id}/animal-count/",
                {"animal_count": animal_count},
            )
            if response is None:
                messages.error(request, "Failed to update animal count.")
            else:
                messages.success(request, "Animal count updated.")

    return redirect("socialmedia:post_detail", post_id=post_id)


@login_required
def update_details(request, post_id):
    """Update camera model, habitat type, and timestamp offset details for a post.
    Restricted to staff and superusers."""
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, "You do not have permission to edit sighting details.")
        return redirect("socialmedia:post_detail", post_id=post_id)

    if request.method == "POST":
        camera_model = request.POST.get("camera_model", "").strip()

        # Extract timestamp offset fields
        incorrect_date = request.POST.get("incorrect_date", "").strip()
        correct_date = request.POST.get("correct_date", "").strip()
        incorrect_time = request.POST.get("incorrect_time", "").strip()
        correct_time = request.POST.get("correct_time", "").strip()

        # Build timestamp offset JSON if any fields are filled
        timestamp_offset_json = None
        if any([incorrect_date, correct_date, incorrect_time, correct_time]):
            timestamp_offset_data = {}
            if incorrect_date:
                timestamp_offset_data["incorrectDate"] = incorrect_date
            if correct_date:
                timestamp_offset_data["correctDate"] = correct_date
            if incorrect_time:
                timestamp_offset_data["incorrectTime"] = incorrect_time
            if correct_time:
                timestamp_offset_data["correctTime"] = correct_time
            timestamp_offset_json = json.dumps(timestamp_offset_data)

        api_token = request.session.get("backend_api_token")
        if api_token:
            api_client = BackendAPIClient(auth_token=api_token)
            payload = {
                "postId": str(post_id),
            }
            if camera_model:
                payload["cameraModel"] = camera_model
            if timestamp_offset_json:
                payload["timestampOffsetErrorDetails"] = timestamp_offset_json

            response = api_client.post(
                "/v1/socialmedia/api/posts/edit/",
                payload,
            )
            if response is None:
                messages.error(request, "Failed to update sighting details.")
            else:
                messages.success(request, "Sighting details updated successfully.")

    return redirect("socialmedia:post_detail", post_id=post_id)


@login_required
def update_location(request, post_id):
    """Update latitude, longitude, privacy setting, and obfuscation radius for a post.
    Restricted to staff and superusers."""
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, "You do not have permission to edit location.")
        return redirect("socialmedia:post_detail", post_id=post_id)

    if request.method == "POST":
        latitude = request.POST.get("location_latitude", "").strip()
        longitude = request.POST.get("location_longitude", "").strip()
        privacy_setting = request.POST.get("privacy_setting", "").strip()
        obfuscation_km = request.POST.get("obfuscation_kilometers", "0.5").strip()
        accuracy_ring_radius_meters = request.POST.get("accuracy_ring_radius_meters", "").strip()

        if not latitude or not longitude:
            messages.error(request, "Latitude and longitude are required.")
            return redirect("socialmedia:post_detail", post_id=post_id)

        api_token = request.session.get("backend_api_token")
        if api_token:
            api_client = BackendAPIClient(auth_token=api_token)
            payload = {
                "latitude": latitude,
                "longitude": longitude,
                "privacy_setting": privacy_setting,
                "obfuscation_kilometers": obfuscation_km,
            }
            if accuracy_ring_radius_meters:
                payload["accuracy_ring_radius_meters"] = accuracy_ring_radius_meters
            response = api_client.post(
                f"/v1/socialmedia/api/posts/{post_id}/location/",
                payload,
            )
            if response is None:
                messages.error(request, "Failed to update location.")
            else:
                messages.success(request, "Location updated.")

    return redirect("socialmedia:post_detail", post_id=post_id)


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
    location_filter = request.GET.get("location", "global")
    user_filter = request.GET.get("user_filter", "all")
    user_display_name_filter = request.GET.get("user_display_name", "").strip()

    # Custom radius filter parameters
    center_lat, center_lon, radius_km = _parse_radius_params(request)

    # ZIP code boundary filter parameters
    zip_code_boundary = request.GET.get("zip_code_boundary", "").strip()
    zip_code_country = request.GET.get("zip_code_country", "US").upper()

    # Place name filter parameters
    place_name = request.GET.get("place_name", "").strip()
    place_country = request.GET.get("place_country", "US").upper()
    place_radius = request.GET.get("place_radius", "10").strip()
    try:
        place_radius = float(place_radius) if place_radius else 10.0
    except ValueError:
        place_radius = 10.0

    # Build API request data
    api_client = BackendAPIClient(auth_token=api_token)
    data = {}

    if species_filter:
        data["species"] = species_filter

    if (
        location_filter == "radius"
        and center_lat is not None
        and center_lon is not None
        and radius_km is not None
        and radius_km > 0
    ):
        data["distanceRadius"] = radius_km
        data["userLatitude"] = center_lat
        data["userLongitude"] = center_lon

    # ZIP code boundary filter
    if location_filter == "zipcode" and zip_code_boundary:
        data["zipCodeBoundary"] = zip_code_boundary
        data["zipCodeCountry"] = zip_code_country

    # Place name filter
    elif location_filter == "place" and place_name:
        data["placeName"] = place_name
        data["placeCountry"] = place_country
        data["placeRadius"] = place_radius

    # User filter
    if user_filter == "self":
        backend_user_id = request.session.get("backend_user_id")
        if backend_user_id:
            data["userId"] = backend_user_id
    elif user_filter == "other" and user_display_name_filter:
        data["userDisplayName"] = user_display_name_filter

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
