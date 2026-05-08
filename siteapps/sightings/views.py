import base64
import json
import logging
import re
import xml.etree.ElementTree as ET

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils.decorators import method_decorator
from django.views import View
from rest_framework import authentication, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from siteapps.sightings.throttles import ReverseGeocodePerDayThrottle, ReverseGeocodePerMinuteThrottle
from siteapps.sightings.utils import reverse_geocode_with_nominatim
from siteapps.socialmedia.web_views import _normalize_post
from siteapps.users.api_client import BackendAPIClient

logger = logging.getLogger(__name__)


def _parse_gpx_track(gpx_file_obj):
    """Parse an open GPX file-like object; return [[lng, lat], ...] for a GeoJSON LineString."""
    try:
        tree = ET.parse(gpx_file_obj)
        root = tree.getroot()
        ns_match = re.match(r"\{[^}]*\}", root.tag)
        ns = ns_match.group(0) if ns_match else ""
        coords = []
        for trkpt in root.iter(f"{ns}trkpt"):
            coords.append([float(trkpt.get("lon")), float(trkpt.get("lat"))])
        return coords
    except Exception:
        return []


@method_decorator(login_required, name="dispatch")
class CreateSightingView(View):
    """Handle wildlife sighting submission"""

    template_name = "sightings/create_sighting.html"

    def get(self, request):
        """Display sighting submission form"""
        # Fetch user's default license to pre-select in the form
        default_license = "cc0"
        is_expert = False
        api_token = request.session.get("backend_api_token")
        if api_token:
            api_client = BackendAPIClient(auth_token=api_token)
            profile = api_client.get_profile()
            if profile:
                default_license = profile.get("default_license", "cc0")
                is_expert = profile.get("is_expert", False)
        return render(request, self.template_name, {"default_license": default_license, "is_expert": is_expert})

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
            "privacySetting": request.POST.get("privacy_setting", "obscured"),
            "accuracyMeters": float(request.POST.get("location_accuracy_meters", 5)),  # Default 5m accuracy
        }

        # Bulk upload sightings are always public — GPS coords come from EXIF and
        # the user is explicitly logging a walk, so obscuring them defeats the purpose.
        if request.POST.get("is_bulk_upload"):
            data["privacySetting"] = settings.PRIVACY_SETTING_PUBLIC

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

        # Handle multi-species list (name="species_list" multi-value field, up to 5)
        species_names = [s.strip() for s in request.POST.getlist("species_list") if s.strip()][:5]
        if species_names:
            data["speciesList"] = species_names
        elif request.POST.get("species"):
            data["species"] = request.POST.get("species")

        # Number of animals in the sighting
        animal_count_raw = request.POST.get("animal_count", "").strip()
        if animal_count_raw:
            try:
                data["animalCount"] = int(animal_count_raw)
            except ValueError:
                pass

        if request.POST.get("post_body"):
            data["postBody"] = request.POST.get("post_body")
        if request.POST.get("location_accuracy_meters"):
            data["accuracyMeters"] = float(request.POST.get("location_accuracy_meters"))
        obfuscation_km = request.POST.get("obfuscation_kilometers", "").strip()
        if obfuscation_km:
            data["obfuscationKilometers"] = obfuscation_km
        elif data.get("privacySetting") == "obscured":
            data["obfuscationKilometers"] = 2  # Default 2km when obscured and not explicitly set
        if request.POST.get("camera_model"):
            data["cameraModel"] = request.POST.get("camera_model")
        if request.POST.get("camera_deployment_date"):
            data["cameraDeploymentDate"] = request.POST.get("camera_deployment_date")

        # Handle timestamp offset details - combine 4 fields into JSON
        incorrect_date = request.POST.get("incorrect_date", "").strip()
        correct_date = request.POST.get("correct_date", "").strip()
        incorrect_time = request.POST.get("incorrect_time", "").strip()
        correct_time = request.POST.get("correct_time", "").strip()

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
            data["timestampOffsetErrorDetails"] = json.dumps(timestamp_offset_data)

        if request.POST.get("sighting_type"):
            data["sightingType"] = request.POST.get("sighting_type")
        if request.POST.get("license_code"):
            data["licenseCode"] = request.POST.get("license_code")
        if request.POST.get("attribution_override"):
            data["attributionOverride"] = request.POST.get("attribution_override")

        speciesnet_predictions_raw = request.POST.get("speciesnet_predictions")
        if speciesnet_predictions_raw:
            try:
                data["speciesnetPredictions"] = json.loads(speciesnet_predictions_raw)
            except (json.JSONDecodeError, ValueError):
                pass  # Ignore malformed predictions JSON

        # Handle media upload
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

        # Handle multiple media upload - convert to base64 array if provided
        media_files = request.FILES.getlist("media_files")
        max_files = 5

        if media_files:
            if len(media_files) > max_files:
                messages.error(request, f"You can only upload up to {max_files} files.")
                return self.get(request)

            media_list = []
            for idx, media_file in enumerate(media_files):
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
                                f"Video file '{media_file.name}' is too large. Maximum size is 500MB. Your file: {len(file_bytes)/(1024*1024):.1f}MB",
                            )
                            return self.get(request)

                    encoded_bytes = base64.b64encode(file_bytes).decode("utf-8")
                    media_list.append({"mediaBytes": encoded_bytes, "isVideo": is_video, "displayOrder": idx + 1})

                    logger.info(
                        f"Encoded media file {idx + 1}: {media_file.name}, size: {len(file_bytes)} bytes, isVideo: {is_video}, content_type: {content_type}"
                    )
                except Exception as e:
                    logger.error(f"Error encoding media file {media_file.name}: {e}")
                    messages.error(request, f"Failed to process media file '{media_file.name}'. Please try again.")
                    return self.get(request)

            # Add media array to data
            data["mediaList"] = media_list

            # For backwards compatibility, also set the first media as primary
            if media_list:
                data["mediaBytes"] = media_list[0]["mediaBytes"]
                data["isVideo"] = media_list[0]["isVideo"]

        # Submit to backend API
        api_client = BackendAPIClient(auth_token=api_token)

        # Submit sighting
        response = api_client.post("/v1/socialmedia/api/posts/create/", data)

        if response and response.get("status") == "success":
            if not request.POST.get("is_bulk_upload"):
                messages.success(request, "Sighting submitted successfully!")
            else:
                bulk_upload_id = request.POST.get("bulk_upload_id")
                post_id = response.get("post_id")
                if bulk_upload_id and post_id:
                    try:
                        api_client.post(
                            f"/v1/socialmedia/api/bulk-upload/{bulk_upload_id}/add-post/",
                            {"post_id": post_id},
                        )
                    except Exception as e:
                        logger.warning(f"Could not record bulk upload sighting association: {e}")
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
        response = api_client.post(
            "/v1/socialmedia/api/feed/get/?limit=500&offset=0",
            {"userId": str(request.user.id)},
        )
        if response:
            sightings = [_normalize_post(p) for p in response.get("results", [])]
        else:
            logger.error("Failed to fetch sightings from backend API for user %s", request.user.id)
            messages.error(request, "Unable to load your sightings at this time. Please try again later.")

    context = {
        "sightings": sightings,
    }
    return render(request, "sightings/my_sightings.html", context)


@login_required
def sightings_map(request):
    """Display the interactive sightings map.

    Sighting data is loaded asynchronously by the map JS using the bbox endpoint,
    so no backend fetch is performed here.
    """
    return render(request, "sightings/sightings_map.html")


@login_required
def sightings_by_bbox(request):
    """Proxy bounding box clustering query to the backend API.

    Accepts a POST body with minLatitude, maxLatitude, minLongitude, maxLongitude,
    and zoom, then delegates clustering entirely to the backend's PostGIS endpoint.
    Returns the backend's GeoJSON FeatureCollection unchanged.
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    api_token = request.session.get("backend_api_token")
    if not api_token:
        return JsonResponse({"error": "Not authenticated"}, status=401)

    payload = {
        "minLatitude": data.get("minLatitude"),
        "maxLatitude": data.get("maxLatitude"),
        "minLongitude": data.get("minLongitude"),
        "maxLongitude": data.get("maxLongitude"),
        "zoom": data.get("zoom", 10),
    }

    api_client = BackendAPIClient(auth_token=api_token)
    response = api_client.post("/v1/socialmedia/api/feed/clusters/", payload)

    if response is None:
        return JsonResponse({"error": "Failed to fetch clusters from backend"}, status=502)

    return JsonResponse(response)


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


# ==========================================
# Bulk Upload Tracking Endpoint
# ==========================================


@method_decorator(login_required, name="dispatch")
class StartBulkUploadView(APIView):
    """Create a bulk upload session on the backend and return its ID."""

    authentication_classes = [authentication.SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        api_token = request.session.get("backend_api_token")
        if not api_token:
            return Response({"error": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED)

        name = request.data.get("name", "").strip() or "Bulk Upload"
        image_count = int(request.data.get("image_count", 0))

        api_client = BackendAPIClient(auth_token=api_token)
        result = api_client.post(
            "/v1/socialmedia/api/bulk-upload/",
            {"name": name, "image_count": image_count},
        )
        if result is None:
            return Response({"error": "Failed to create bulk upload session."}, status=status.HTTP_502_BAD_GATEWAY)

        session_id = result["id"]

        # Forward GPX file to backend if provided
        gpx_file = request.FILES.get("gpx_file")
        if gpx_file:
            api_client.post_file(
                f"/v1/socialmedia/api/bulk-upload/{session_id}/gpx/",
                files={"gpx_file": (gpx_file.name, gpx_file, gpx_file.content_type or "application/gpx+xml")},
            )

        # Forward bird calls GeoJSON file to backend if provided
        bird_calls_file = request.FILES.get("bird_calls_file")
        if bird_calls_file:
            api_client.post_file(
                f"/v1/socialmedia/api/bulk-upload/{session_id}/bird-calls/",
                files={
                    "bird_calls_file": (
                        bird_calls_file.name,
                        bird_calls_file,
                        bird_calls_file.content_type or "application/geo+json",
                    )
                },
            )

        return Response(
            {"id": session_id, "name": result["name"], "cover_image_url": None},
            status=status.HTTP_201_CREATED,
        )


# ==========================================
# Sighting Type Proxy Endpoint
# ==========================================


def proxy_sighting_types(request):
    """Proxy to backend API for fetching sighting types (public endpoint)."""
    api_client = BackendAPIClient()  # No auth token needed for public endpoint
    result = api_client.get("/v1/socialmedia/api/sighting-types/")

    if result is not None:
        # Backend returns a list of sighting types
        return JsonResponse(result, safe=False)
    else:
        return JsonResponse({"error": "Failed to fetch sighting types"}, status=500)


# ==========================================
# Site Configuration Proxy Endpoint
# ==========================================


def proxy_site_config(request):
    """Proxy to backend API for fetching site configuration (public endpoint)."""
    api_client = BackendAPIClient()  # No auth token needed for public endpoint
    result = api_client.get("/v1/socialmedia/api/site-config/")

    if result is not None:
        # Backend returns site configuration object
        return JsonResponse(result)
    else:
        return JsonResponse({"error": "Failed to fetch site configuration"}, status=500)


# ==========================================
# User Sighting Location Proxy Endpoints
# ==========================================


@login_required
def list_user_locations(request):
    """Proxy to backend API for listing user's saved locations."""
    api_token = request.session.get("backend_api_token")
    if not api_token:
        return JsonResponse({"error": "Authentication required."}, status=401)

    api_client = BackendAPIClient(auth_token=api_token)
    result = api_client.get("/v1/socialmedia/api/locations/")

    if result is not None:
        # Backend returns a list directly
        return JsonResponse(result, safe=False)
    else:
        return JsonResponse({"error": "Failed to fetch locations"}, status=500)


@login_required
def create_user_location(request):
    """Proxy to backend API for creating a new saved location."""
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    api_token = request.session.get("backend_api_token")
    if not api_token:
        return JsonResponse({"error": "Authentication required."}, status=401)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    api_client = BackendAPIClient(auth_token=api_token)
    result = api_client.post("/v1/socialmedia/api/locations/create/", data)

    if result is not None:
        # Backend returns the created location dict with 201 status
        return JsonResponse(result)
    else:
        return JsonResponse({"error": "Failed to create location"}, status=500)


@login_required
def update_user_location(request, location_id):
    """Proxy to backend API for updating a saved location."""
    if request.method != "PUT":
        return JsonResponse({"error": "PUT required"}, status=405)

    api_token = request.session.get("backend_api_token")
    if not api_token:
        return JsonResponse({"error": "Authentication required."}, status=401)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    api_client = BackendAPIClient(auth_token=api_token)
    result = api_client.put(f"/v1/socialmedia/api/locations/{location_id}/", data)

    if result is not None:
        return JsonResponse(result)
    else:
        return JsonResponse({"error": "Failed to update location"}, status=500)


@login_required
def delete_user_location(request, location_id):
    """Proxy to backend API for deleting a saved location."""
    if request.method != "DELETE":
        return JsonResponse({"error": "DELETE required"}, status=405)

    api_token = request.session.get("backend_api_token")
    if not api_token:
        return JsonResponse({"error": "Authentication required."}, status=401)

    api_client = BackendAPIClient(auth_token=api_token)
    result = api_client.delete(f"/v1/socialmedia/api/locations/{location_id}/delete/")

    if result is not None:
        return JsonResponse({"status": "success"})
    else:
        return JsonResponse({"error": "Failed to delete location"}, status=500)


@method_decorator(login_required, name="dispatch")
class ManageLocationsView(View):
    """Redirect to profile page which now hosts the Saved Locations section."""

    def get(self, request):
        return redirect("users:profile")


@method_decorator(login_required, name="dispatch")
class BulkUploadHistoryView(View):
    """List the current user's bulk upload sessions (fetched from backend)."""

    template_name = "sightings/bulk_upload_history.html"

    def get(self, request):
        api_token = request.session.get("backend_api_token")
        uploads = []
        if api_token:
            api_client = BackendAPIClient(auth_token=api_token)
            result = api_client.get("/v1/socialmedia/api/bulk-upload/list/")
            if result is not None:
                uploads = result
        return render(request, self.template_name, {"uploads": uploads})


@method_decorator(login_required, name="dispatch")
class BulkUploadDetailView(View):
    """Show the sightings belonging to a specific bulk upload session."""

    template_name = "sightings/bulk_upload_detail.html"

    def get(self, request, pk):
        from django.http import Http404

        api_token = request.session.get("backend_api_token")
        if not api_token:
            raise Http404

        api_client = BackendAPIClient(auth_token=api_token)

        # Fetch the session (post_ids + gpx_track coords) from backend
        session = api_client.get(f"/v1/socialmedia/api/bulk-upload/{pk}/")
        if session is None:
            raise Http404

        post_ids = session.get("post_ids", [])
        sightings = []

        if post_ids:
            response = api_client.post(
                f"/v1/socialmedia/api/feed/get/?limit={len(post_ids)}&offset=0",
                {"postIds": post_ids},
            )
            if response:
                sightings = [_normalize_post(p) for p in response.get("results", [])]

        # Sort by encounter_datetime (actual photo capture time), oldest first by default.
        sort_order = request.GET.get("sort", "asc")
        sightings.sort(key=lambda p: p.get("encounter_datetime") or "", reverse=(sort_order == "desc"))

        # Build GeoJSON-ready list of sightings that have real coordinates.
        sightings_geo = []
        for s in sightings:
            if s.get("geoprivacy") == settings.PRIVACY_SETTING_PRIVATE:
                continue
            lat = s.get("latitude")
            lng = s.get("longitude")
            if lat is None or lng is None:
                continue
            try:
                sightings_geo.append(
                    {
                        "id": str(s.get("id", "")),
                        "lat": float(lat),
                        "lng": float(lng),
                        "title": s.get("title") or "",
                        "species": s.get("species") or (s.get("species_list") or [""])[0] or "",
                    }
                )
            except (ValueError, TypeError):
                pass

        # GPX track returned by backend as [[lng, lat], ...] (already parsed coords)
        gpx_track = session.get("gpx_track", [])

        # Bird calls GeoJSON FeatureCollection (or None)
        bird_calls = session.get("bird_calls")

        return render(
            request,
            self.template_name,
            {
                "upload": session,
                "sightings": sightings,
                "sort_order": sort_order,
                "sightings_geo": sightings_geo,
                "gpx_track": gpx_track,
                "bird_calls": bird_calls,
            },
        )


@login_required
def upload_bulk_upload_gpx(request, pk):
    """Accept a GPX file POST and proxy it to the backend bulk upload session."""
    from django.http import Http404

    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    api_token = request.session.get("backend_api_token")
    if not api_token:
        raise Http404

    gpx_file = request.FILES.get("gpx_file")
    if not gpx_file:
        messages.error(request, "No GPX file selected.")
        return redirect("sightings:bulk_upload_detail", pk=pk)

    api_client = BackendAPIClient(auth_token=api_token)
    result = api_client.post_file(
        f"/v1/socialmedia/api/bulk-upload/{pk}/gpx/",
        files={"gpx_file": (gpx_file.name, gpx_file, gpx_file.content_type or "application/gpx+xml")},
    )
    if result is None:
        messages.error(request, "Failed to upload GPX track.")
    else:
        messages.success(request, "GPX track uploaded.")
    return redirect("sightings:bulk_upload_detail", pk=pk)


@login_required
def upload_bulk_upload_bird_calls(request, pk):
    """Accept a GeoJSON file POST and proxy it to the backend bulk upload session."""
    from django.http import Http404

    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    api_token = request.session.get("backend_api_token")
    if not api_token:
        raise Http404

    bird_calls_file = request.FILES.get("bird_calls_file")
    if not bird_calls_file:
        messages.error(request, "No bird calls GeoJSON file selected.")
        return redirect("sightings:bulk_upload_detail", pk=pk)

    api_client = BackendAPIClient(auth_token=api_token)
    result = api_client.post_file(
        f"/v1/socialmedia/api/bulk-upload/{pk}/bird-calls/",
        files={
            "bird_calls_file": (
                bird_calls_file.name,
                bird_calls_file,
                bird_calls_file.content_type or "application/geo+json",
            )
        },
    )
    if result is None:
        messages.error(request, "Failed to upload bird calls.")
    else:
        messages.success(request, f"Bird calls uploaded ({result.get('feature_count', '?')} calls).")
    return redirect("sightings:bulk_upload_detail", pk=pk)


@login_required
def rename_bulk_upload(request, pk):
    """PATCH the bulk upload session name via the backend API."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    api_token = request.session.get("backend_api_token")
    if not api_token:
        return JsonResponse({"error": "Authentication required."}, status=401)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    new_name = data.get("name", "").strip()
    if not new_name:
        return JsonResponse({"error": "name is required."}, status=400)

    api_client = BackendAPIClient(auth_token=api_token)
    result = api_client.patch(f"/v1/socialmedia/api/bulk-upload/{pk}/", {"name": new_name})
    if result is None:
        return JsonResponse({"error": "Failed to rename session."}, status=502)
    return JsonResponse(result)
