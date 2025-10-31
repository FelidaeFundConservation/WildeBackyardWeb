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
    SearchSuggestionsPerDayThrottle,
    SearchSuggestionsPerMinuteThrottle,
)


# Create your views here.
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
