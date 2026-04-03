"""Management command: load_inat_taxonomy

Fetches North American vertebrate species (excluding Actinopterygii) from the
iNaturalist open taxonomy API and populates the Taxon + TaxonName tables.

Usage:
    python manage.py load_inat_taxonomy [--settings=config.settings.local]

Strategy:
    Uses iNaturalist taxon_id for each vertebrate class to fetch all species,
    sorted by observation count descending. North American species naturally
    dominate the top of the list. The --min-observations flag (default 1)
    prunes taxa with very few observations (likely non-NA exotics or data
    entry errors).

    iNat class taxon IDs:
        Aves      = 3
        Mammalia  = 40151
        Reptilia  = 26036
        Amphibia  = 20978
        (Actinopterygii = 47178 — intentionally excluded)

Options:
    --groups           Comma-separated iNat class names.
    --min-observations Minimum observation count to include (default: 1)
    --rank             Taxonomic rank to load (default: species)
    --no-common-names  Skip TaxonName entries (faster dry-run)
"""

import time

import requests
from django.core.management.base import BaseCommand, CommandError

from siteapps.species.models import VERTEBRATE_ICONIC_GROUPS, Taxon, TaxonName

INAT_API_BASE = "https://api.inaturalist.org/v1"

ICONIC_TAXON_IDS = {
    "Aves": 3,
    "Mammalia": 40151,
    "Reptilia": 26036,
    "Amphibia": 20978,
}

MAX_PER_PAGE = 200
REQUEST_DELAY_SECONDS = 1.1


def _get_taxa_page(session, taxon_id, rank, page):
    resp = session.get(
        f"{INAT_API_BASE}/taxa",
        params={
            "taxon_id": taxon_id,
            "rank": rank,
            "is_active": "true",
            "per_page": MAX_PER_PAGE,
            "page": page,
            "order": "desc",
            "order_by": "observations_count",
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


class Command(BaseCommand):
    help = (
        "Load North American vertebrate species from the iNaturalist taxonomy API "
        "into the Taxon and TaxonName tables. Excludes Actinopterygii (ray-finned fish)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--groups",
            default=",".join(VERTEBRATE_ICONIC_GROUPS),
            help="Comma-separated iconic group names to load (default: Aves,Mammalia,Reptilia,Amphibia)",
        )
        parser.add_argument(
            "--rank",
            default="species",
            help="Taxonomic rank to load (default: species)",
        )
        parser.add_argument(
            "--min-observations",
            type=int,
            default=1,
            help="Minimum iNat observation count to include a taxon (default: 1)",
        )
        parser.add_argument(
            "--no-common-names",
            action="store_true",
            default=False,
            help="Skip writing TaxonName rows (faster; only updates Taxon core fields)",
        )

    def handle(self, *args, **options):
        groups = [g.strip() for g in options["groups"].split(",") if g.strip()]
        rank = options["rank"]
        skip_names = options["no_common_names"]
        min_obs = options["min_observations"]

        if not groups:
            raise CommandError("--groups must contain at least one iconic taxon name.")

        if "Actinopterygii" in groups:
            self.stderr.write(
                self.style.WARNING(
                    "Actinopterygii is included in --groups. " "The default behaviour excludes ray-finned fish."
                )
            )

        unknown = [g for g in groups if g not in ICONIC_TAXON_IDS]
        if unknown:
            raise CommandError(f"Unknown group(s): {unknown}. " f"Valid values: {list(ICONIC_TAXON_IDS.keys())}")

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"Loading iNat taxonomy: rank={rank}, groups={groups}, " f"min_observations={min_obs}"
            )
        )

        session = requests.Session()
        session.headers.update({"User-Agent": "WildeBackyard/1.0 (wildlife conservation)"})

        total_created = 0
        total_updated = 0
        total_names = 0
        total_skipped = 0

        for group in groups:
            taxon_id = ICONIC_TAXON_IDS[group]
            self.stdout.write(f"\n  Processing group: {group} (iNat taxon_id={taxon_id})")
            group_count = 0
            page = 1

            while True:
                try:
                    data = _get_taxa_page(session, taxon_id, rank, page)
                except requests.RequestException as exc:
                    self.stderr.write(self.style.ERROR(f"    API error on page {page}: {exc}"))
                    break

                results = data.get("results", [])
                if not results:
                    break

                total_results = data.get("total_results", 0)
                page_skipped = 0

                for item in results:
                    obs_count = item.get("observations_count", 0)
                    if obs_count < min_obs:
                        page_skipped += 1
                        total_skipped += 1
                        continue

                    inat_id = item["id"]
                    defaults = {
                        "name": item.get("name", ""),
                        "rank": item.get("rank", rank),
                        "rank_level": item.get("rank_level"),
                        "iconic_taxon_name": item.get("iconic_taxon_name", group),
                        "ancestry": item.get("ancestry", ""),
                        "parent_id": item.get("parent_id"),
                        "preferred_common_name": item.get("preferred_common_name", ""),
                        "is_active": item.get("is_active", True),
                        "observations_count": obs_count,
                    }
                    taxon, created = Taxon.objects.update_or_create(
                        inat_id=inat_id,
                        defaults=defaults,
                    )
                    if created:
                        total_created += 1
                    else:
                        total_updated += 1

                    if not skip_names:
                        taxon.names.all().delete()

                        common = item.get("preferred_common_name", "")
                        if common:
                            TaxonName.objects.create(
                                taxon=taxon,
                                name=common,
                                lexicon="English",
                                is_valid=True,
                                position=0,
                            )
                            total_names += 1

                        TaxonName.objects.create(
                            taxon=taxon,
                            name=item.get("name", ""),
                            lexicon="Scientific Names",
                            is_valid=True,
                            position=0,
                        )
                        total_names += 1

                group_count += len(results) - page_skipped
                self.stdout.write(
                    f"    Page {page}: {len(results) - page_skipped} loaded, "
                    f"{page_skipped} skipped "
                    f"({group_count}/{total_results} for {group})"
                )

                if group_count + total_skipped >= total_results or len(results) < MAX_PER_PAGE:
                    break

                page += 1
                time.sleep(REQUEST_DELAY_SECONDS)

            self.stdout.write(self.style.SUCCESS(f"  {group}: {group_count} species loaded"))

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone. Created: {total_created}, Updated: {total_updated}, "
                f"Skipped (low obs): {total_skipped}, Names stored: {total_names}"
            )
        )
