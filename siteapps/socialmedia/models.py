import uuid

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from model_utils.models import TimeStampedModel
from simple_history.models import HistoricalRecords

from siteapps.species.models import SpeciesName, Taxon

User = get_user_model()


# Images or videos
class Media(TimeStampedModel):
    # UUID for the image
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Assuming all media is either images or videos, so using a boolean field
    is_video = models.BooleanField(default=False)

    # The path to the media file in storage
    file_cloud_path = models.CharField(max_length=250)

    # Unique content identifier for deduplication
    content_hash = models.CharField(max_length=64)

    # The user who uploaded the media
    uploaded_by = models.ForeignKey(User, related_name="uploaded_by_user", on_delete=models.SET_NULL, null=True)


# Base post class, used for replies to posts
class TextComment(TimeStampedModel):
    # UUID for the post
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # The user who posted the comment
    created_by = models.ForeignKey(User, related_name="created_by_user", on_delete=models.SET_NULL, null=True)

    # The text content of the comment
    text_content = models.TextField(max_length=4000, null=True)

    # Like count
    upvoted_by = models.ManyToManyField(User, blank=True, related_name="upvoted_by")


# A specialized post with media and title, used for main posts
class MediaPost(TextComment):
    # Relative second-level comments in reply to this post
    replies = models.ManyToManyField(TextComment, related_name="post_replies", blank=True)

    # Title of the post
    title = models.TextField(max_length=80)

    # The media the comment contains, if any
    media = models.ForeignKey(Media, related_name="post_media", on_delete=models.SET_NULL, null=True)

    # Circle radius where the true point may be within
    accuracy_ring_radius_meters = models.IntegerField(null=True)

    # When the encounter occurred
    encounter_datetime = models.DateTimeField()

    # All media types are collapsed into a single model for query performance,
    # Field names are differentiated for security (i.e public latitude, private latitude, etc.)
    geoprivacy = models.CharField(
        choices=(
            (1, settings.PRIVACY_SETTING_PUBLIC),
            (2, settings.PRIVACY_SETTING_OBSCURED),
            (3, settings.PRIVACY_SETTING_PRIVATE),
        ),
        max_length=16,
    )

    # The species the user specified was sighted
    species = models.ForeignKey(SpeciesName, on_delete=models.SET_NULL, null=True, blank=True)
    # iNaturalist-derived taxon FK (replaces species FK over time)
    taxon = models.ForeignKey(Taxon, on_delete=models.SET_NULL, null=True, blank=True, related_name="media_posts")

    ########################
    # Public Information
    ########################
    # The location of the post, only used if public location is given.
    public_location_latitude = models.FloatField(null=True)
    public_location_longitude = models.FloatField(null=True)

    # Length of one side of the obfuscation box
    obfuscation_range_kilometers = models.FloatField(null=True)

    # Coordinates of each corner of the box. This should be randomly offset.
    # This is shown publicly in place of the true coordinate.
    # The number order matters for drawing the box client-side.
    obfuscation_box_corner_1_latitude = models.FloatField(null=True)
    obfuscation_box_corner_1_longitude = models.FloatField(null=True)

    obfuscation_box_corner_2_latitude = models.FloatField(null=True)
    obfuscation_box_corner_2_longitude = models.FloatField(null=True)

    obfuscation_box_corner_3_latitude = models.FloatField(null=True)
    obfuscation_box_corner_3_longitude = models.FloatField(null=True)

    obfuscation_box_corner_4_latitude = models.FloatField(null=True)
    obfuscation_box_corner_4_longitude = models.FloatField(null=True)

    # Human readable location info
    geocoded_location_locality = models.CharField(max_length=64, null=True)
    geocoded_location_state = models.CharField(max_length=64, null=True)
    geocoded_location_country = models.CharField(max_length=64, null=True)
    geocoded_location_zip_code = models.CharField(max_length=64, null=True)

    # Supplementary info to understand the submission
    camera_model = models.CharField(max_length=64, null=True)
    camera_deployment_date = models.CharField(max_length=32, null=True)
    camera_timestamp_offset_error_details = models.CharField(max_length=512, null=True)

    habitat_type = models.CharField(max_length=64, null=True)

    ##############################
    # (!!!) Private Information
    ##############################
    # The true, unobfuscated location available privately, if obfuscation was selected.
    # THIS SHOULD NEVER BE ACCESSIBLE/SENT TO THE PUBLIC VIA THE APP/API
    true_location_latitude = models.FloatField(null=True)
    true_location_longitude = models.FloatField(null=True)

    # The private location.
    # THIS SHOULD NEVER BE ACCESSIBLE/SENT TO THE PUBLIC VIA THE APP/API
    private_location_latitude = models.FloatField(null=True)
    private_location_longitude = models.FloatField(null=True)


# Model to handle reports for inappropriate content
class InappropriateContentReport(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Who reported the media/comment
    reported_by = models.ForeignKey(User, related_name="reported_by_user", on_delete=models.SET_NULL, null=True)

    # The user the report was made against
    reported_user = models.ForeignKey(User, related_name="reported_user", on_delete=models.SET_NULL, null=True)

    # Can report either comments or posts
    reported_comment = models.ForeignKey(
        TextComment, related_name="reported_comment", on_delete=models.SET_NULL, null=True, blank=True
    )
    reported_post = models.ForeignKey(
        MediaPost, related_name="reported_post", on_delete=models.SET_NULL, null=True, blank=True
    )

    # Whether the report has been handled by a moderator/staff
    resolved = models.BooleanField(default=False)

    # Describes the offense the user was warned for (if any)
    warning_notes = models.CharField(max_length=800, default="")
