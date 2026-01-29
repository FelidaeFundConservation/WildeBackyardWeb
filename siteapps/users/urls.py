from django.urls import path

from .views import (
    ChangeUsernameView,
    DeleteAccountView,
    LoginView,
    LogoutView,
    PasswordResetRequestView,
    ProfileView,
    RegisterView,
    ResendVerificationView,
)

app_name = "users"

urlpatterns = [
    path("login/", LoginView.as_view(), name="login"),
    path("register/", RegisterView.as_view(), name="register"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("profile/", ProfileView.as_view(), name="profile"),
    path("profile/change-username/", ChangeUsernameView.as_view(), name="change_username"),
    path("profile/delete-account/", DeleteAccountView.as_view(), name="delete_account"),
    path("password-reset/", PasswordResetRequestView.as_view(), name="password_reset"),
    path("resend-verification/", ResendVerificationView.as_view(), name="resend_verification"),
]
