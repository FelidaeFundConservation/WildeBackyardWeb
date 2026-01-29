import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.decorators import method_decorator
from django.views import View

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

        # Extract form data
        data = {
            "species": request.POST.get("species"),
            "post_title": request.POST.get("post_title"),
            "post_body": request.POST.get("post_body"),
            "encounter_date": request.POST.get("encounter_date"),
            "encounter_time": request.POST.get("encounter_time"),
            "location_latitude": request.POST.get("location_latitude"),
            "location_longitude": request.POST.get("location_longitude"),
            "location_accuracy_meters": request.POST.get("location_accuracy_meters", 0),
            "privacy_setting": request.POST.get("privacy_setting", "public"),
            "obfuscation_kilometers": request.POST.get("obfuscation_kilometers", 1),
            "camera_model": request.POST.get("camera_model"),
            "camera_deployment_date": request.POST.get("camera_deployment_date"),
            "habitat_type": request.POST.get("habitat_type"),
            "timestamp_offset_details": request.POST.get("timestamp_offset_details"),
        }

        # Handle media upload
        media_file = request.FILES.get("media_file")

        # Validation
        if not data["post_title"]:
            messages.error(request, "Post title is required.")
            return self.get(request)

        if not data["encounter_date"]:
            messages.error(request, "Encounter date is required.")
            return self.get(request)

        if not data["location_latitude"] or not data["location_longitude"]:
            messages.error(request, "Location is required.")
            return self.get(request)

        # Submit to backend API
        api_client = BackendAPIClient(auth_token=api_token)

        # If media file exists, upload it first
        media_url = None
        if media_file:
            upload_response = api_client.upload_media(media_file)
            if upload_response and upload_response.get("status") == "success":
                media_url = upload_response.get("body", {}).get("media_url")

        # Add media URL to data
        if media_url:
            data["media_url"] = media_url

        # Submit sighting
        response = api_client.post("/socialmedia/api/post/create/", data)

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
    api_token = request.session.get("backend_api_token")
    sightings = []

    if api_token:
        api_client = BackendAPIClient(auth_token=api_token)
        response = api_client.get("/socialmedia/api/feed/get/", {"user_posts_only": True})
        if response and response.get("status") == "success":
            sightings = response.get("body", {}).get("posts", [])

    context = {
        "sightings": sightings,
    }
    return render(request, "sightings/my_sightings.html", context)
