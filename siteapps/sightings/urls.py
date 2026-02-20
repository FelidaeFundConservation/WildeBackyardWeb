from django.urls import path

from . import views
from .views import ReverseGeocodeWithNominatim

app_name = "sightings"

urlpatterns = [
    path("create/", views.CreateSightingView.as_view(), name="create"),
    path("my-sightings/", views.my_sightings, name="my_sightings"),
    path("map/", views.sightings_map, name="map"),
    path("api/bbox/", views.sightings_by_bbox, name="bbox"),
    path("api/reverse_geocode/", ReverseGeocodeWithNominatim.as_view(), name="reverse_geocode"),
]
