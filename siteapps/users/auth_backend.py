"""
Authentication backend that uses the WildeBackyardBackend REST API
"""

import logging

import requests
from django.conf import settings
from django.contrib.auth.backends import BaseBackend

from siteapps.users.models import User

logger = logging.getLogger(__name__)


class BackendAPIAuthBackend(BaseBackend):
    """
    Authenticate against the WildeBackyardBackend REST API.

    This backend forwards authentication requests to the Backend API
    and creates/updates local user records based on the API response.
    """

    def authenticate(self, request, email=None, password=None, **kwargs):
        """
        Authenticate user against the Backend API.

        Args:
            request: The current request object
            email: User's email address
            password: User's password

        Returns:
            User object if authentication succeeds, None otherwise
        """
        if email is None or password is None:
            return None

        try:
            # Call Backend API login endpoint
            api_url = f"{settings.BACKEND_API_URL}/v1/users/login/"
            response = requests.post(api_url, json={"email": email, "password": password}, timeout=10)

            if response.status_code == 200:
                data = response.json()
                auth_token = data.get("key")

                if not auth_token:
                    logger.warning(f"Authentication successful but no token returned for {email}")
                    return None

                # Fetch user profile from Backend API
                profile_url = f"{settings.BACKEND_API_URL}/v1/users/profile/"
                profile_response = requests.get(
                    profile_url, headers={"Authorization": f"Token {auth_token}"}, timeout=10
                )

                if profile_response.status_code == 200:
                    profile_data = profile_response.json()

                    # Create or update local user record
                    user, created = User.objects.get_or_create(
                        email=email,
                        defaults={
                            "name": profile_data.get("display_name", email.split("@")[0]),
                            "is_staff": profile_data.get("is_staff", False),
                            "is_superuser": profile_data.get("is_superuser", False),
                        },
                    )

                    # Update user attributes from API
                    if not created:
                        user.name = profile_data.get("display_name", user.name)
                        user.is_staff = profile_data.get("is_staff", False)
                        user.is_superuser = profile_data.get("is_superuser", False)
                        user.save()

                    # Store the API token and user ID in the session for future API calls
                    if request:
                        request.session["backend_api_token"] = auth_token
                        request.session["backend_user_id"] = profile_data.get("id")

                    logger.info(f"Successfully authenticated user {email} via Backend API")
                    return user
                else:
                    logger.warning(f"Failed to fetch profile for {email}: {profile_response.status_code}")
                    return None
            else:
                logger.info(f"Authentication failed for {email}: {response.status_code}")
                return None

        except requests.exceptions.RequestException as e:
            logger.error(f"Backend API connection error during authentication: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error during authentication: {e}")
            return None

    def get_user(self, user_id):
        """
        Get user by ID for session management.

        Args:
            user_id: The user's primary key

        Returns:
            User object if found, None otherwise
        """
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
