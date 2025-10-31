from django.urls import path, re_path

from siteapps.mapbox.views import GetMapboxGeocode, GetMapboxLocationSearchSuggestions

urlpatterns = [
    path("api/search_suggestions/", GetMapboxLocationSearchSuggestions.as_view(), name="search_suggestions"),
    path("api/geocode/", GetMapboxGeocode.as_view(), name="geocode"),
]
