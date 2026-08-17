# Licensed under the MIT License.
# See LICENSE file in the project root for full license information.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("sightings", "0004_remove_bulkupload_cover_image_and_more"),
    ]

    operations = [
        migrations.DeleteModel(
            name="BulkUploadSighting",
        ),
        migrations.DeleteModel(
            name="BulkUpload",
        ),
    ]
