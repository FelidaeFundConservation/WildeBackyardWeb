"""
Management command: set_bulk_upload_sightings_public

Updates the geoprivacy of every sighting that belongs to a BulkUpload
to "public" by calling the backend EditPost API on behalf of each post's
owner.

Usage:
    uv run python manage.py set_bulk_upload_sightings_public \
        --settings=config.settings.local [--dry-run]
"""

import logging

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from siteapps.sightings.models import BulkUpload
from siteapps.users.api_client import BackendAPIClient

logger = logging.getLogger(__name__)
User = get_user_model()


class Command(BaseCommand):
    help = "Set geoprivacy=public for all sightings that belong to a BulkUpload."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Print what would be done without calling the backend API.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        uploads = BulkUpload.objects.prefetch_related("sightings", "user").all()
        total_uploads = uploads.count()
        self.stdout.write(f"Found {total_uploads} bulk upload(s).")

        updated = 0
        skipped = 0
        errors = 0

        for upload in uploads:
            user = upload.user

            # We need an API token for this user.  Try the local token store first.
            # BackendAPIClient expects a raw DRF token string.
            from rest_framework.authtoken.models import Token as DRFToken

            try:
                token_obj = DRFToken.objects.get(user=user)
                api_token = token_obj.key
            except DRFToken.DoesNotExist:
                self.stderr.write(
                    self.style.WARNING(
                        f"  No API token found for user {user} — skipping {upload.sightings.count()} sighting(s) "
                        f"from upload '{upload.name}'."
                    )
                )
                skipped += upload.sightings.count()
                continue

            api_client = BackendAPIClient(auth_token=api_token)

            for bulk_sighting in upload.sightings.all():
                post_id = str(bulk_sighting.backend_post_id)
                if dry_run:
                    self.stdout.write(f"  [dry-run] Would set post {post_id} → public")
                    updated += 1
                    continue

                resp = api_client.post(
                    "/v1/socialmedia/api/posts/edit/",
                    {"postId": post_id, "privacySetting": "public"},
                )
                if resp is None:
                    self.stderr.write(self.style.ERROR(f"  ERROR updating post {post_id}"))
                    errors += 1
                else:
                    self.stdout.write(f"  ✓ post {post_id} → public")
                    updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone. updated={updated}  skipped={skipped}  errors={errors}"
                + (" (dry-run, no changes made)" if dry_run else "")
            )
        )
