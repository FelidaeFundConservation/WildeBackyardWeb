"""
Client for interacting with the WildeBackyardBackend REST API
"""

import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class BackendAPIClient:
    """Client for making requests to the WildeBackyardBackend API"""

    def __init__(self, auth_token=None):
        """
        Initialize the API client.

        Args:
            auth_token: Optional authentication token for authenticated requests
        """
        self.base_url = settings.BACKEND_API_URL
        self.auth_token = auth_token
        self.timeout = 30

    @property
    def headers(self):
        """Get headers for API requests"""
        headers = {"Content-Type": "application/json"}
        if self.auth_token:
            headers["Authorization"] = f"Token {self.auth_token}"
        return headers

    def get(self, endpoint, params=None):
        """
        Make a GET request to the Backend API.

        Args:
            endpoint: API endpoint path (e.g., '/v1/species/api/list/')
            params: Optional query parameters dict

        Returns:
            dict: Response data if successful, None otherwise
        """
        try:
            url = f"{self.base_url}{endpoint}"
            response = requests.get(url, params=params, headers=self.headers, timeout=self.timeout)

            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"GET request failed for {endpoint}: {response.status_code}")
                return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Backend API connection error during GET {endpoint}: {e}")
            return None

    def post(self, endpoint, data=None):
        """
        Make a POST request to the Backend API.

        Args:
            endpoint: API endpoint path
            data: Data to send in the request body

        Returns:
            dict: Response data if successful, None otherwise
        """
        try:
            url = f"{self.base_url}{endpoint}"
            response = requests.post(url, json=data, headers=self.headers, timeout=self.timeout)

            if response.status_code in [200, 201]:
                # 201 Created may have empty body
                if response.text:
                    return response.json()
                else:
                    return {"status": "success"}
            else:
                logger.warning(f"POST request failed for {endpoint}: {response.status_code}")
                return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Backend API connection error during POST {endpoint}: {e}")
            return None

    def put(self, endpoint, data=None):
        try:
            url = f"{self.base_url}{endpoint}"
            response = requests.put(url, json=data, headers=self.headers, timeout=self.timeout)
            if response.status_code in [200, 204]:
                return response.json() if response.text else {"status": "success"}
            else:
                logger.warning(f"PUT request failed for {endpoint}: {response.status_code}")
                return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Backend API connection error during PUT {endpoint}: {e}")
            return None

    def patch(self, endpoint, data=None):
        try:
            url = f"{self.base_url}{endpoint}"
            response = requests.patch(url, json=data, headers=self.headers, timeout=self.timeout)
            if response.status_code in [200, 204]:
                return response.json() if response.text else {"status": "success"}
            else:
                logger.warning(f"PATCH request failed for {endpoint}: {response.status_code}")
                return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Backend API connection error during PATCH {endpoint}: {e}")
            return None

    def delete(self, endpoint):
        try:
            url = f"{self.base_url}{endpoint}"
            response = requests.delete(url, headers=self.headers, timeout=self.timeout)
            if response.status_code in [200, 204]:
                return {}
            else:
                logger.warning(f"DELETE request failed for {endpoint}: {response.status_code}")
                return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Backend API connection error during DELETE {endpoint}: {e}")
            return None

    def post_file(self, endpoint, files, data=None):
        """Make a multipart/form-data POST (for file uploads such as GPX tracks).

        Args:
            endpoint: API endpoint path
            files: dict mapping field name to file-like object, e.g. {"gpx_file": open(...)}
            data: optional extra form fields dict

        Returns:
            dict: Response data if successful, None otherwise
        """
        try:
            url = f"{self.base_url}{endpoint}"
            # Do NOT set Content-Type here — requests sets the correct multipart boundary automatically.
            headers = {}
            if self.auth_token:
                headers["Authorization"] = f"Token {self.auth_token}"
            response = requests.post(url, files=files, data=data or {}, headers=headers, timeout=self.timeout)
            if response.status_code in [200, 201]:
                return response.json() if response.text else {"status": "success"}
            else:
                logger.warning(f"POST file request failed for {endpoint}: {response.status_code}")
                return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Backend API connection error during POST file {endpoint}: {e}")
            return None

    def register_user(self, email, password, name=None):
        """
        Register a new user via the Backend API.

        Args:
            email: User's email address
            password: User's password
            name: Optional display name

        Returns:
            tuple: (success: bool, data: dict or error_message: str)
        """
        try:
            url = f"{self.base_url}/v1/users/register/"
            data = {
                "email": email,
                "password1": password,
                "password2": password,
            }
            if name:
                data["name"] = name

            response = requests.post(url, json=data, headers=self.headers, timeout=self.timeout)

            if response.status_code in [200, 201, 204]:
                # 204 No Content means success but no response body
                result = response.json() if response.status_code != 204 else {"email": email}
                return (True, result)
            else:
                error_data = response.json() if response.headers.get("content-type") == "application/json" else {}
                logger.warning(f"User registration failed: {response.status_code} - {error_data}")

                # Extract error messages
                error_messages = []
                for _field, errors in error_data.items():
                    if isinstance(errors, list):
                        error_messages.extend(errors)
                    else:
                        error_messages.append(str(errors))

                error_text = " ".join(error_messages) if error_messages else "Registration failed. Please try again."
                return (False, error_text)
        except requests.exceptions.RequestException as e:
            logger.error(f"Backend API connection error during registration: {e}")
            return (False, "Unable to connect to registration service. Please try again later.")

    def login(self, email, password):
        """
        Login user via the Backend API.

        Args:
            email: User's email address
            password: User's password

        Returns:
            dict: Response data with auth token if successful, None otherwise
        """
        try:
            url = f"{self.base_url}/v1/users/login/"
            data = {"email": email, "password": password}

            response = requests.post(url, json=data, headers=self.headers, timeout=self.timeout)

            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Login failed: {response.status_code}")
                return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Backend API connection error during login: {e}")
            return None

    def logout(self):
        """
        Logout user via the Backend API.

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            url = f"{self.base_url}/v1/users/logout/"
            response = requests.post(url, headers=self.headers, timeout=self.timeout)
            return response.status_code == 200
        except requests.exceptions.RequestException as e:
            logger.error(f"Backend API connection error during logout: {e}")
            return False

    def get_profile(self):
        """
        Get user profile from the Backend API.

        Returns:
            dict: Profile data if successful, None otherwise
        """
        try:
            url = f"{self.base_url}/v1/users/profile/"
            response = requests.get(url, headers=self.headers, timeout=self.timeout)

            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Failed to fetch profile: {response.status_code}")
                return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Backend API connection error during profile fetch: {e}")
            return None

    def change_username(self, new_username):
        """
        Change username via the Backend API.

        Args:
            new_username: New display name

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            url = f"{self.base_url}/v1/users/profile/change_username"
            data = {"newUsername": new_username}

            response = requests.post(url, json=data, headers=self.headers, timeout=self.timeout)
            return response.status_code == 200
        except requests.exceptions.RequestException as e:
            logger.error(f"Backend API connection error during username change: {e}")
            return False

    def update_default_license(self, license_code):
        """
        Update the user's default sighting license via the Backend API.

        Args:
            license_code: License code string (e.g. 'cc0', 'cc-by')

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            url = f"{self.base_url}/v1/users/profile/update-default-license/"
            response = requests.post(
                url, json={"licenseCode": license_code}, headers=self.headers, timeout=self.timeout
            )
            return response.status_code == 200
        except requests.exceptions.RequestException as e:
            logger.error(f"Backend API connection error during default license update: {e}")
            return False

    def delete_account(self, confirmation_string):
        """
        Delete user account via the Backend API.

        Args:
            confirmation_string: Username confirmation for deletion

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            url = f"{self.base_url}/v1/users/delete_account"
            data = {"confirmationString": confirmation_string}

            response = requests.post(url, json=data, headers=self.headers, timeout=self.timeout)
            return response.status_code == 200
        except requests.exceptions.RequestException as e:
            logger.error(f"Backend API connection error during account deletion: {e}")
            return False

    def request_password_reset(self, email):
        """
        Request password reset via the Backend API.

        Args:
            email: User's email address

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            url = f"{self.base_url}/v1/account/password_reset/"
            data = {"email": email}

            response = requests.post(url, json=data, headers=self.headers, timeout=self.timeout)
            return response.status_code == 200
        except requests.exceptions.RequestException as e:
            logger.error(f"Backend API connection error during password reset: {e}")
            return False

    def change_password(self, old_password, new_password1, new_password2):
        """
        Change the authenticated user's password via the Backend API.

        Args:
            old_password: The user's current password
            new_password1: The new password
            new_password2: Confirmation of the new password

        Returns:
            (bool, str): (True, "") on success, (False, error_message) on failure
        """
        try:
            url = f"{self.base_url}/v1/users/profile/change-password/"
            data = {
                "old_password": old_password,
                "new_password1": new_password1,
                "new_password2": new_password2,
            }
            response = requests.post(url, json=data, headers=self.headers, timeout=self.timeout)
            if response.status_code == 200:
                return True, ""
            elif response.status_code == 400:
                errors = response.json()
                # Flatten all error messages into a single string
                messages = []
                for field_errors in errors.values():
                    if isinstance(field_errors, list):
                        messages.extend(field_errors)
                    else:
                        messages.append(str(field_errors))
                return False, " ".join(messages)
            else:
                return False, "Failed to change password."
        except requests.exceptions.RequestException as e:
            logger.error(f"Backend API connection error during password change: {e}")
            return False, "Connection error. Please try again."
