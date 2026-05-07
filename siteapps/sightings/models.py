import uuid

from django.contrib.auth import get_user_model
from django.db import models
from model_utils.models import TimeStampedModel

User = get_user_model()


class BulkUpload(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="bulk_uploads")
    name = models.CharField(max_length=255)
    image_count = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.name} ({self.image_count} images) — {self.created:%Y-%m-%d %H:%M}"

    def add_sighting(self, backend_post_id):
        return BulkUploadSighting.objects.create(bulk_upload=self, backend_post_id=backend_post_id)


class BulkUploadSighting(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    bulk_upload = models.ForeignKey(BulkUpload, on_delete=models.CASCADE, related_name="sightings")
    backend_post_id = models.UUIDField(db_index=True)

    def __str__(self):
        return f"Sighting {self.backend_post_id} — {self.bulk_upload.name}"
