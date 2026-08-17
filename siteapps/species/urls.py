# Licensed under the MIT License.
# See LICENSE file in the project root for full license information.

from django.urls import path

from siteapps.species.views import CreateSpeciesNameView, GetSpeciesNamesView, SuggestSpeciesView, TaxonAutocompleteView

app_name = "species"

urlpatterns = [
    path("api/names/get/", GetSpeciesNamesView.as_view(), name="get_species"),
    path("api/names/create/", CreateSpeciesNameView.as_view(), name="create_species"),
    path("api/suggest/", SuggestSpeciesView.as_view(), name="suggest_species"),
    path("api/taxa/autocomplete/", TaxonAutocompleteView.as_view(), name="taxa_autocomplete"),
]
