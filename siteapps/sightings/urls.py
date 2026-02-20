from django.urls import path

from . import views

app_name = "sightings"

urlpatterns = [
    path("create/", views.CreateSightingView.as_view(), name="create"),
    path("my-sightings/", views.my_sightings, name="my_sightings"),
    path("map/", views.sightings_map, name="map"),
]
