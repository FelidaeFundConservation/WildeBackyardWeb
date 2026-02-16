import json

import requests
from django.conf import settings
from django.shortcuts import render
from rest_framework import authentication, permissions, status
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .throttles import (
    GeocodePerDayThrottle,
    GeocodePerMinuteThrottle,
    ReverseGeocodePerDayThrottle,
    ReverseGeocodePerMinuteThrottle,
    SearchSuggestionsPerDayThrottle,
    SearchSuggestionsPerMinuteThrottle,
)


# Create your views here.
# Note: MapLibre GL JS is used for map rendering in the frontend,
# but these geocoding/search APIs still use Mapbox services since
# MapLibre doesn't provide geocoding functionality.
class GetMapboxLocationSearchSuggestions(APIView):
    authentication_classes = [authentication.TokenAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [SearchSuggestionsPerMinuteThrottle, SearchSuggestionsPerDayThrottle]

    def post(self, request):
        data = json.loads(request.body)

        search_text = data.get("searchText")

        api_url = "https://api.mapbox.com/search/searchbox/v1/suggest?"

        response = requests.get(
            url=f"{api_url}q={search_text}&limit=4&access_token={settings.MAPBOX_SECRET_TOKEN}&session_token={request.user.id}&types=poi,address"
        )

        if response.status_code == 200:
            data = json.loads(response.content)

            # Last element of list is metadata, so it should be removed
            suggestions = [(location["name"], location["full_address"]) for location in data["suggestions"]]

            return Response(status=status.HTTP_200_OK, data={"suggestions": suggestions})
        else:
            return Response(
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class GetMapboxGeocode(APIView):
    authentication_classes = [authentication.TokenAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [GeocodePerMinuteThrottle, GeocodePerDayThrottle]

    def post(self, request):
        data = json.loads(request.body)

        address = data.get("address")

        api_url = "https://api.mapbox.com/search/geocode/v6/forward?"

        response = requests.get(url=f"{api_url}q={address}&limit=1&access_token={settings.MAPBOX_SECRET_TOKEN}")

        if response.status_code == 200:
            data = json.loads(response.content)
            coordinates = data["features"][0]["geometry"]["coordinates"]

            return Response(status=status.HTTP_200_OK, data={"coordinates": coordinates})
        else:
            return Response(
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ReverseGeocodeWithNominatim(APIView):
    """
    Reverse geocode lat/lon coordinates using Nominatim API.
    This is used to get human-readable location information from coordinates.
    """
    authentication_classes = [authentication.TokenAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [ReverseGeocodePerMinuteThrottle, ReverseGeocodePerDayThrottle]

    def post(self, request):
        data = json.loads(request.body)

        latitude = data.get("latitude")
        longitude = data.get("longitude")

        if not latitude or not longitude:
            return Response(
                status=status.HTTP_400_BAD_REQUEST,
                data={"error": "latitude and longitude are required"}
            )

        # Nominatim API endpoint for reverse geocoding
        # Using OpenStreetMap's public Nominatim instance
        api_url = "https://nominatim.openstreetmap.org/reverse"
        
        # Per Nominatim usage policy, we must include a User-Agent
        headers = {
            "User-Agent": "WildeBackyard/1.0 (wildlife conservation platform)"
        }

        params = {
            "lat": latitude,
            "lon": longitude,
            "format": "json",
            "addressdetails": 1,
            "zoom": 18,  # Highest detail level
        }

        try:
            response = requests.get(api_url, params=params, headers=headers, timeout=10)

            if response.status_code == 200:
                data = response.json()
                
                # Extract address components
                address = data.get("address", {})
                
                # Build location data from Nominatim response
                location_data = {
                    "locality": (
                        address.get("city") or 
                        address.get("town") or 
                        address.get("village") or 
                        address.get("hamlet") or
                        address.get("suburb") or
                        None
                    ),
                    "state": (
                        address.get("state") or 
                        address.get("province") or
                        None
                    ),
                    "country": address.get("country"),
                    "zip_code": address.get("postcode"),
                }

                return Response(status=status.HTTP_200_OK, data=location_data)
            else:
                return Response(
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    data={"error": "Failed to reverse geocode coordinates"}
                )
        except requests.exceptions.RequestException as e:
            return Response(
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                data={"error": f"Request failed: {str(e)}"}
            )
