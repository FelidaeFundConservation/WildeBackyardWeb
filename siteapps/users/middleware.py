import logging
import time

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

_REFRESH_INTERVAL = 300  # seconds (5 minutes)


class RefreshStaffFlagsMiddleware:
    """
    Middleware that keeps the local user record's is_staff / is_superuser flags
    in sync with the Backend API profile.

    Runs at most once every 5 minutes per session (tracked via session key
    ``_staff_flags_refreshed_at``) so the backend API is not hammered on every
    request.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            token = request.session.get("backend_api_token")
            last_refresh = request.session.get("_staff_flags_refreshed_at", 0)
            now = time.time()

            if token and (now - last_refresh) > _REFRESH_INTERVAL:
                try:
                    profile_url = f"{settings.BACKEND_API_URL}/v1/users/profile/"
                    resp = requests.get(
                        profile_url,
                        headers={"Authorization": f"Token {token}"},
                        timeout=5,
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        is_staff = data.get("is_staff", False)
                        is_superuser = data.get("is_superuser", False)
                        user = request.user
                        if user.is_staff != is_staff or user.is_superuser != is_superuser:
                            user.is_staff = is_staff
                            user.is_superuser = is_superuser
                            user.save(update_fields=["is_staff", "is_superuser"])
                        request.session["_staff_flags_refreshed_at"] = now
                except Exception as e:
                    logger.warning("RefreshStaffFlagsMiddleware: could not refresh flags: %s", e)

        return self.get_response(request)
