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
    # User location management
    path("api/backend/locations/", views.list_user_locations, name="list_locations"),
    path("api/backend/locations/create/", views.create_user_location, name="create_location"),
    path("api/backend/locations/<uuid:location_id>/", views.update_user_location, name="update_location"),
    path("api/backend/locations/<uuid:location_id>/delete/", views.delete_user_location, name="delete_location"),
]
