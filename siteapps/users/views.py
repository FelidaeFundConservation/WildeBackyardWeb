import logging

import requests
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic.base import View as BaseView

from siteapps.users.api_client import BackendAPIClient
from siteapps.users.models import User

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name="dispatch")
class LoginView(View):
    """Handle user login via Backend API"""

    template_name = "users/login.html"

    def get(self, request):
        """Display login form"""
        if request.user.is_authenticated:
            return redirect("home:home")
        return render(request, self.template_name)

    def post(self, request):
        """Process login form"""
        email = request.POST.get("email")
        password = request.POST.get("password")

        if not email or not password:
            messages.error(request, "Please provide both email and password.")
            return render(request, self.template_name)

        # Authenticate using the Backend API auth backend
        user = authenticate(request, email=email, password=password)

        if user is not None:
            login(request, user)
            messages.success(request, f"Welcome back, {user.name}!")
            return redirect(request.GET.get("next", "home:home"))
        else:
            messages.error(request, "Invalid email or password.")
            return render(request, self.template_name)


class RegisterView(View):
    """Handle user registration via Backend API"""

    template_name = "users/register.html"

    def get(self, request):
        """Display registration form"""
        if request.user.is_authenticated:
            return redirect("home:home")
        return render(request, self.template_name)

    def post(self, request):
        """Process registration form"""
        email = request.POST.get("email")
        password = request.POST.get("password")
        password_confirm = request.POST.get("password_confirm")
        name = request.POST.get("name", "")

        # Validation
        if not email or not password:
            messages.error(request, "Email and password are required.")
            return render(request, self.template_name)

        if password != password_confirm:
            messages.error(request, "Passwords do not match.")
            return render(request, self.template_name)

        if len(password) < 8:
            messages.error(request, "Password must be at least 8 characters long.")
            return render(request, self.template_name)

        # Register via Backend API
        api_client = BackendAPIClient()
        success, result = api_client.register_user(email, password, name)

        if success:
            # Auto-login after successful registration
            user = authenticate(request, email=email, password=password)
            if user is not None:
                login(request, user)
                messages.success(
                    request, f"Welcome to WildeBackyard, {user.name}! Please check your email to verify your account."
                )
                return redirect("home:home")
            else:
                # Registration succeeded but auto-login failed
                messages.success(
                    request, "Registration successful! Please check your email to verify your account, then log in."
                )
                return redirect("users:login")
        else:
            # Display the specific error from the API
            messages.error(request, result)
            return render(request, self.template_name)


class LogoutView(BaseView):
    """Handle user logout"""

    def get(self, request):
        """Handle GET requests for logout"""
        return self.post(request)

    def post(self, request):
        """Process logout"""
        # Logout from Backend API if token exists
        api_token = request.session.get("backend_api_token")
        if api_token:
            api_client = BackendAPIClient(auth_token=api_token)
            api_client.logout()
            del request.session["backend_api_token"]

        logout(request)
        messages.success(request, "You have been logged out.")
        return redirect("home:home")


class ProfileView(LoginRequiredMixin, View):
    """Display user profile"""

    template_name = "users/profile.html"

    def get(self, request):
        """Display profile page"""
        # Get profile data from Backend API
        api_token = request.session.get("backend_api_token")
        profile_data = None

        if api_token:
            api_client = BackendAPIClient(auth_token=api_token)
            profile_data = api_client.get_profile()

        context = {
            "user": request.user,
            "profile_data": profile_data,
        }
        return render(request, self.template_name, context)


class ChangeUsernameView(LoginRequiredMixin, View):
    """Handle username change via Backend API"""

    def post(self, request):
        """Process username change"""
        new_username = request.POST.get("new_username")

        if not new_username or len(new_username) < 3:
            messages.error(request, "Username must be at least 3 characters long.")
            return redirect("users:profile")

        # Change username via Backend API
        api_token = request.session.get("backend_api_token")
        if api_token:
            api_client = BackendAPIClient(auth_token=api_token)
            success = api_client.change_username(new_username)

            if success:
                # Update local user record
                request.user.name = new_username
                request.user.save()
                messages.success(request, "Username updated successfully!")
            else:
                messages.error(request, "Failed to update username.")
        else:
            messages.error(request, "Authentication required.")

        return redirect("users:profile")


class DeleteAccountView(LoginRequiredMixin, View):
    """Handle account deletion via Backend API"""

    def post(self, request):
        """Process account deletion"""
        confirmation = request.POST.get("confirmation")

        if confirmation != request.user.name:
            messages.error(request, "Confirmation string does not match your username.")
            return redirect("users:profile")

        # Delete account via Backend API
        api_token = request.session.get("backend_api_token")
        if api_token:
            api_client = BackendAPIClient(auth_token=api_token)
            success = api_client.delete_account(confirmation)

            if success:
                # Delete local user record
                request.user.delete()
                logout(request)
                messages.success(request, "Your account has been deleted.")
                return redirect("home:home")
            else:
                messages.error(request, "Failed to delete account.")
        else:
            messages.error(request, "Authentication required.")

        return redirect("users:profile")


class PasswordResetRequestView(View):
    """Request password reset via Backend API"""

    template_name = "users/password_reset_request.html"

    def get(self, request):
        """Display password reset request form"""
        return render(request, self.template_name)

    def post(self, request):
        """Process password reset request"""
        email = request.POST.get("email")

        if not email:
            messages.error(request, "Email address is required.")
            return render(request, self.template_name)

        # Request password reset via Backend API
        api_client = BackendAPIClient()
        success = api_client.request_password_reset(email)

        if success:
            messages.success(request, "Password reset instructions have been sent to your email.")
            return redirect("users:login")
        else:
            # Don't reveal whether email exists for security
            messages.success(request, "If the email exists, password reset instructions have been sent.")
            return redirect("users:login")


class ResendVerificationView(LoginRequiredMixin, View):
    """Resend email verification via Backend API"""

    def post(self, request):
        """Resend verification email"""
        api_token = request.session.get("backend_api_token")

        if not api_token:
            messages.error(request, "Authentication required.")
            return redirect("users:login")

        # Call backend API to resend verification
        api_client = BackendAPIClient(auth_token=api_token)
        try:
            url = f"{api_client.base_url}/v1/users/resend_verification_email/"
            response = requests.post(url, headers=api_client.headers, timeout=api_client.timeout)

            if response.status_code == 200:
                messages.success(request, "Verification email has been sent.")
            else:
                messages.error(request, "Failed to send verification email.")
        except Exception as e:
            logger.error(f"Error resending verification: {e}")
            messages.error(request, "Failed to send verification email.")

        return redirect("users:profile")
