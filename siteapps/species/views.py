import json

from django.shortcuts import render
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from similarity.similarity import suggest_species
from siteapps.species.models import SpeciesName, Taxon


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

    Queries Taxon.preferred_common_name and Taxon.name (scientific) for matches.
    Falls back to legacy SpeciesName list if Taxon table is empty.

    Response:
        {"choice": "Coyote", "scientific_name": "Canis latrans",
         "iconic_taxon_name": "Mammalia", "total": 0.87, "confident": true}
        {"choice": null}
    """

    authentication_classes = []
    permission_classes = []

    def get(self, request):
        candidate = request.query_params.get("q", "").strip()
        if not candidate:
            return Response({"choice": None})

        # Build a lookup dict: display_name -> Taxon row (or None for legacy)
        taxon_by_name = {}
        taxa_qs = Taxon.objects.filter(is_active=True).values(
            "id", "inat_id", "name", "preferred_common_name", "iconic_taxon_name"
        )
        if taxa_qs.exists():
            for t in taxa_qs:
                common = t["preferred_common_name"]
                sci = t["name"]
                if common:
                    taxon_by_name[common] = t
                # Scientific name also matchable but keyed separately
                taxon_by_name.setdefault(sci, t)
            choices = list(taxon_by_name.keys())
        else:
            # Legacy fallback: flat SpeciesName list
            choices = list(SpeciesName.objects.values_list("name", flat=True))
            taxon_by_name = {}

        result = suggest_species(candidate, choices)
        if result is None:
            return Response({"choice": None})

        matched_choice = result["choice"]
        taxon = taxon_by_name.get(matched_choice)
        if taxon:
            # Return human-readable common name as the choice
            return Response(
                {
                    "choice": taxon["preferred_common_name"] or taxon["name"],
                    "scientific_name": taxon["name"],
                    "iconic_taxon_name": taxon["iconic_taxon_name"],
                    "inat_id": taxon["inat_id"],
                    "total": result["total"],
                    "confident": result["confident"],
                }
            )
        return Response(result)


class TaxonAutocompleteView(APIView):
    """Return up to 10 taxa matching a partial common or scientific name.

    GET /species/api/taxa/autocomplete/?q=<term>

    Response:
        {"results": [{"id": 1, "inat_id": 9788, "name": "Turdus migratorius",
                      "preferred_common_name": "American Robin",
                      "iconic_taxon_name": "Aves"}, ...]}
    """

    authentication_classes = []
    permission_classes = []

    def get(self, request):
        from django.db.models import Q

        q = request.query_params.get("q", "").strip()
        if len(q) < 2:
            return Response({"results": []})

        taxa = (
            Taxon.objects.filter(is_active=True)
            .filter(Q(preferred_common_name__icontains=q) | Q(name__icontains=q))
            .order_by("-observations_count")
            .values("id", "inat_id", "name", "preferred_common_name", "iconic_taxon_name")[:10]
        )
        return Response({"results": list(taxa)})
