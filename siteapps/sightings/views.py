import base64
import json
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.decorators import method_decorator
from django.views import View
from rest_framework import authentication, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from siteapps.sightings.throttles import ReverseGeocodePerDayThrottle, ReverseGeocodePerMinuteThrottle
from siteapps.sightings.utils import reverse_geocode_with_nominatim
from siteapps.socialmedia.models import MediaPost
from siteapps.socialmedia.views import format_post
from siteapps.socialmedia.web_views import _normalize_post
from siteapps.users.api_client import BackendAPIClient

logger = logging.getLogger(__name__)


@method_decorator(login_required, name="dispatch")
class CreateSightingView(View):
    """Handle wildlife sighting submission"""

    template_name = "sightings/create_sighting.html"

    def get(self, request):
        """Display sighting submission form"""
        # Get species list from backend (no auth required for species list)
        species_list = []

        try:
            api_client = BackendAPIClient()
            response = api_client.get("/v1/species/api/names/get/")
            if response and "species_names" in response:
                # Backend returns a flat list of species names
                species_list = response.get("species_names", [])
                logger.info(f"Loaded {len(species_list)} species from backend API")
            else:
                logger.warning(f"Failed to load species list. Response: {response}")
        except Exception as e:
            logger.error(f"Error loading species list: {e}")

        context = {
            "species_list": species_list,
        }
        return render(request, self.template_name, context)

    def post(self, request):
        """Process sighting submission"""
        api_token = request.session.get("backend_api_token")

        if not api_token:
            messages.error(request, "Authentication required.")
            return redirect("users:login")

        # Extract form data and transform to camelCase format for backend API
        encounter_date = request.POST.get("encounter_date")
        encounter_time = request.POST.get("encounter_time", "12:00")
        encounter_datetime = f"{encounter_date} {encounter_time}" if encounter_date else None

        # Get coordinates
        try:
            latitude = float(request.POST.get("location_latitude")) if request.POST.get("location_latitude") else None
            longitude = (
                float(request.POST.get("location_longitude")) if request.POST.get("location_longitude") else None
            )
        except (ValueError, TypeError):
            messages.error(request, "Invalid latitude or longitude values.")
            return self.get(request)

        # Reverse geocode the coordinates using Nominatim
        geocoded_location = None
        if latitude and longitude:
            geocoded_location = reverse_geocode_with_nominatim(latitude, longitude)
            if geocoded_location:
                logger.info(f"Reverse geocoded location: {geocoded_location}")

        # Required fields
        data = {
            "postTitle": request.POST.get("post_title"),
            "encounterDatetime": encounter_datetime,
            "latitude": latitude,
            "longitude": longitude,
            "privacySetting": request.POST.get("privacy_setting", "approximate"),
            "accuracyMeters": float(request.POST.get("location_accuracy_meters", 5)),  # Default 5m accuracy
        }

        # Add geocoded location data if available
        if geocoded_location:
            if geocoded_location.get("country"):
                data["geocodedLocationCountry"] = geocoded_location["country"]
            if geocoded_location.get("state"):
                data["geocodedLocationState"] = geocoded_location["state"]
            if geocoded_location.get("locality"):
                data["geocodedLocationLocality"] = geocoded_location["locality"]
            if geocoded_location.get("zip_code"):
                data["geocodedLocationZipCode"] = geocoded_location["zip_code"]

        # Optional fields - only include if provided
        if request.POST.get("species"):
            data["species"] = request.POST.get("species")
        if request.POST.get("post_body"):
            data["postBody"] = request.POST.get("post_body")
        if request.POST.get("location_accuracy_meters"):
            data["accuracyMeters"] = float(request.POST.get("location_accuracy_meters"))
        if request.POST.get("obfuscation_kilometers"):
            data["obfuscationKilometers"] = request.POST.get("obfuscation_kilometers")
        if request.POST.get("camera_model"):
            data["cameraModel"] = request.POST.get("camera_model")
        if request.POST.get("camera_deployment_date"):
            data["cameraDeploymentDate"] = request.POST.get("camera_deployment_date")
        if request.POST.get("habitat_type"):
            data["habitatType"] = request.POST.get("habitat_type")
        if request.POST.get("timestamp_offset_details"):
            data["timestampOffsetErrorDetails"] = request.POST.get("timestamp_offset_details")

        # Handle media upload
        media_file = request.FILES.get("media_file")

        # Validation
        if not data["postTitle"]:
            messages.error(request, "Post title is required.")
            return self.get(request)

        if not data["encounterDatetime"]:
            messages.error(request, "Encounter date is required.")
            return self.get(request)

        if not data["latitude"] or not data["longitude"]:
            messages.error(request, "Location is required.")
            return self.get(request)

        # Handle media upload - convert to base64 if provided
        media_file = request.FILES.get("media_file")
        if media_file:
            try:
                # Read the file and encode to base64
                file_bytes = media_file.read()

                # Determine if it's a video based on content type
                content_type = media_file.content_type or ""
                is_video = content_type.startswith("video/")

                # Validate video size (max 500MB)
                if is_video:
                    max_video_size = 500 * 1024 * 1024  # 500MB
                    if len(file_bytes) > max_video_size:
                        messages.error(
                            request,
                            f"Video file is too large. Maximum size is 500MB. Your file: {len(file_bytes)/(1024*1024):.1f}MB",
                        )
                        return self.get(request)

                encoded_bytes = base64.b64encode(file_bytes).decode("utf-8")
                data["mediaBytes"] = encoded_bytes
                data["isVideo"] = is_video

                logger.info(
                    f"Encoded media file: {media_file.name}, size: {len(file_bytes)} bytes, isVideo: {is_video}, content_type: {content_type}"
                )
            except Exception as e:
                logger.error(f"Error encoding media file: {e}")
                messages.error(request, "Failed to process media file. Please try again.")
                return self.get(request)

        # Submit to backend API
        api_client = BackendAPIClient(auth_token=api_token)

        # Submit sighting
        response = api_client.post("/v1/socialmedia/api/posts/create/", data)

        if response and response.get("status") == "success":
            messages.success(request, "Sighting submitted successfully!")
            return redirect("socialmedia:feed")
        else:
            error_msg = "Failed to submit sighting."
            if response and response.get("errors"):
                error_msg = ", ".join(response.get("errors"))
            messages.error(request, error_msg)
            return self.get(request)


@login_required
def my_sightings(request):
    """Display user's sightings"""
    # Query the local database directly — both the web app and backend share
    # the same Cloud SQL database, so posts created via the backend are visible here.
    sightings = [
        _normalize_post(format_post(p)) for p in MediaPost.objects.filter(created_by=request.user).order_by("-created")
    ]

    context = {
        "sightings": sightings,
    }
    return render(request, "sightings/my_sightings.html", context)


@login_required
def sightings_map(request):
    """Display all sightings on an interactive map with clustering"""
    api_token = request.session.get("backend_api_token")
    features = []

    if api_token:
        api_client = BackendAPIClient(auth_token=api_token)
        # Fetch a large batch of sightings for the map
        response = api_client.post("/v1/socialmedia/api/feed/get/?limit=500&offset=0", {})
        if response and response.get("results"):
            for post in response["results"]:
                lat = post.get("latitude")
                lng = post.get("longitude")

                if lat is not None and lng is not None:
                    features.append(
                        {
                            "type": "Feature",
                            "geometry": {"type": "Point", "coordinates": [lng, lat]},
                            "properties": {
                                "id": str(post.get("id", "")),
                                "title": post.get("title", ""),
                                "species": post.get("species", ""),
                                "encounter_date": post.get("encounter_datetime", ""),
                                "geocoded_location": post.get("geocoded_location", ""),
                            },
                        }
                    )

    context = {
        "sightings_geojson": json.dumps({"type": "FeatureCollection", "features": features}),
        "sightings_count": len(features),
    }
    return render(request, "sightings/sightings_map.html", context)


class ReverseGeocodeWithNominatim(APIView):
    """
    Reverse geocode lat/lon coordinates using Nominatim API.
    Returns human-readable location information from coordinates.
    """

    authentication_classes = [authentication.TokenAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [ReverseGeocodePerMinuteThrottle, ReverseGeocodePerDayThrottle]

    def post(self, request):
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return Response(
                status=status.HTTP_400_BAD_REQUEST,
                data={"error": "Invalid JSON in request body"},
            )

        latitude = data.get("latitude")
        longitude = data.get("longitude")

        if latitude is None or longitude is None:
            return Response(
                status=status.HTTP_400_BAD_REQUEST,
                data={"error": "latitude and longitude are required"},
            )

        location_data = reverse_geocode_with_nominatim(latitude, longitude)

        if location_data:
            return Response(status=status.HTTP_200_OK, data=location_data)
        else:
            return Response(
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                data={"error": "Failed to reverse geocode coordinates"},
            )
