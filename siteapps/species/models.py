# Licensed under the MIT License.
# See LICENSE file in the project root for full license information.

from django.db import models
from model_utils.models import TimeStampedModel


# Create your models here.
class SpeciesName(TimeStampedModel):
    name = models.CharField("Common Name", max_length=250, unique=True)
    scientific_name = models.CharField(max_length=250, null=True, blank=True)

    # Species name is currently used and shown in the annotation widget
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = (
            "name",
            "-created",
        )
        verbose_name_plural = "Species List"


# iNaturalist-derived taxonomy
# ---------------------------------------------------------------------------
# Iconic taxon names used to categorise vertebrates (excluding Actinopterygii).
VERTEBRATE_ICONIC_GROUPS = ["Aves", "Mammalia", "Reptilia", "Amphibia"]
# Actinopterygii (ray-finned fish) is intentionally excluded.


class Taxon(models.Model):
    """A taxonomic entity synchronised from the iNaturalist open taxonomy.

    Only North American vertebrates (Aves, Mammalia, Reptilia, Amphibia) at
    species rank are loaded by the load_inat_taxonomy management command.
    """

    inat_id = models.IntegerField(unique=True, db_index=True)
    # Scientific name (e.g. "Turdus migratorius")
    name = models.CharField(max_length=255, db_index=True)
    rank = models.CharField(max_length=50, default="species")  # species/genus/family…
    rank_level = models.FloatField(null=True)
    # High-level group: Aves, Mammalia, Reptilia, Amphibia
    iconic_taxon_name = models.CharField(max_length=50, blank=True, default="", db_index=True)
    ancestry = models.CharField(max_length=500, blank=True, default="")
    parent_id = models.IntegerField(null=True, blank=True)
    preferred_common_name = models.CharField(max_length=255, blank=True, default="", db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    observations_count = models.IntegerField(default=0)
    # Square thumbnail URL from iNaturalist default_photo (CC-licensed, hotlinked from iNat CDN)
    default_photo_url = models.URLField(blank=True, default="")

    class Meta:
        ordering = ("preferred_common_name", "name")
        verbose_name_plural = "Taxa"

    def __str__(self):
        if self.preferred_common_name:
            return f"{self.preferred_common_name} ({self.name})"
        return self.name

    @property
    def display_name(self):
        return self.preferred_common_name or self.name


class TaxonName(models.Model):
    """Additional common or scientific names for a Taxon."""

    taxon = models.ForeignKey(Taxon, related_name="names", on_delete=models.CASCADE)
    name = models.CharField(max_length=255, db_index=True)
    lexicon = models.CharField(max_length=100)  # 'English', 'Scientific Names', …
    is_valid = models.BooleanField(default=True)
    position = models.IntegerField(default=0)

    class Meta:
        ordering = ("lexicon", "position")

    def __str__(self):
        return f"{self.name} [{self.lexicon}]"
