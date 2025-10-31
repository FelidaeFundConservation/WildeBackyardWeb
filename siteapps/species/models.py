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
