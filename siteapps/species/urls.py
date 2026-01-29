from django.urls import path

from siteapps.species.views import CreateSpeciesNameView, GetSpeciesNamesView

app_name = "species"

urlpatterns = [
    path("api/names/get/", GetSpeciesNamesView.as_view(), name="get_species"),
    path("api/names/create/", CreateSpeciesNameView.as_view(), name="create_species"),
]
