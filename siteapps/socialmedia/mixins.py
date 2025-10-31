from django.conf import settings
from rest_framework import status
from rest_framework.response import Response


class LatLngValidationMixin:
    def validate_latitude_longitude(latitude, longitude):
        # Check the values exist
        if not latitude and not longitude:
            return createResponse400("Latitude and longitude values were both not provided.")
        elif not latitude:
            return createResponse400("Latitude value was not provided.")
        elif not longitude:
            return createResponse400("Longitude value was not provided.")

        # If they exist, check the values are valid
        latitude_valid = -90 < float(latitude) < 90
        longitude_valid = -180 < float(longitude) < 180

        if not latitude_valid and not longitude_valid:
            return createResponse400(
                "Both latitude and longitude values are invalid (must provide a value between -90 and 90 for latitude; -180 and 180 for longitude)."
            )
        elif not latitude_valid:
            return createResponse400("Latitude value is invalid (must provide a value between -90 and 90).")
        elif not longitude_valid:
            return createResponse400("Longitude value is invalid (must provide a value between -180 and 180).")
        else:
            return None


class PrivacySettingValidationMixin:
    def validate_privacy_setting(privacy_setting):
        if privacy_setting is None:
            return createResponse400(
                "No privacy setting provided. Please provide a setting ('public', 'obscured', or 'private')."
            )
        elif (
            privacy_setting != settings.PRIVACY_SETTING_PUBLIC
            and privacy_setting != settings.PRIVACY_SETTING_OBSCURED
            and privacy_setting != settings.PRIVACY_SETTING_PRIVATE
        ):
            return createResponse400(
                f"Invalid privacy setting '{privacy_setting}' provided. Must be 'public', 'obscured', or 'private'."
            )
        else:
            return None


# Check whether required combinations of arguments exists
class PostInputsValidationMixin:
    def validate_arguments_exist(
        privacy_setting,
        encounter_datetime,
        accuracy_meters,
        obfuscation_kilometers,
        obfuscation_box_corners,
        geocoded_location_country,
        post_title,
    ):
        # Datetime string to convert
        if encounter_datetime is None:
            return createResponse400("No encounter datetime provided.")

        # A ring where the true location may lie
        if accuracy_meters is None:
            return createResponse400(
                "No location accuracy provided. Must be a meter value above 0, or exactly 0 for 'No Accuracy Info.'"
            )

        # Privacy-setting specific checks
        if privacy_setting == settings.PRIVACY_SETTING_OBSCURED:
            if obfuscation_kilometers is None or int(obfuscation_kilometers) < 1 or int(obfuscation_kilometers) > 10:
                return createResponse400("Invalid obfuscation range. Must be between 1 and 10 kilometers.")

            # 4 corners with latitude and longitude, so 8 values
            if len(obfuscation_box_corners) != 8:
                return createResponse400(
                    f"Invalid number of values for obfuscation box coordinates ({len(obfuscation_box_corners)} provided.)"
                )

        # Check if a post title was given
        if post_title is None:
            return createResponse400("No post title provided.")


def createResponse400(message):
    return Response(
        status=status.HTTP_400_BAD_REQUEST,
        data={"error": message},
    )
