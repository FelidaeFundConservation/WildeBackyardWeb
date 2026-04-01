import json

from django.shortcuts import render
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from similarity.similarity import suggest_species
from siteapps.species.models import SpeciesName


# Create your views here.
class GetSpeciesNamesView(APIView):
    def get(self, request):
        species_names = list(SpeciesName.objects.all().values_list("name", flat=True))
        data = {"species_names": species_names}
        return Response(status=status.HTTP_200_OK, data=data)


class CreateSpeciesNameView(APIView):
    def post(self, request):
        data = json.loads(request.body)

        species_name = data.get("name")

        if species_name is None:
            message = "Species name was not provided."

            return Response(
                status=status.HTTP_400_BAD_REQUEST,
                data={"error": message},
            )
        else:
            # Names should be in title case to avoid duplications
            species_name = species_name.title()
            # Create a new species with name if it doesn't exist
            SpeciesName.objects.get_or_create(name=species_name)

        return Response(status=status.HTTP_201_CREATED)


class SuggestSpeciesView(APIView):
    """Return the best-matching species name for a user's free-text input.

    GET /species/api/suggest/?q=<candidate>

    Response:
        {"choice": "Coyote", "total": 0.87, "confident": true}   — match found
        {"choice": null}                                           — no match (garbage input)
    """

    authentication_classes = []
    permission_classes = []

    def get(self, request):
        candidate = request.query_params.get("q", "").strip()
        if not candidate:
            return Response({"choice": None})
        species_names = list(SpeciesName.objects.values_list("name", flat=True))
        result = suggest_species(candidate, species_names)
        if result is None:
            return Response({"choice": None})
        return Response(result)
