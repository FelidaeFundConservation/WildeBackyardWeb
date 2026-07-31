from django.urls import path

from .views import (
    ChangePasswordView,
    ChangeUsernameView,
    DeleteAccountView,
    LoginView,
    LogoutView,
    PasswordResetRequestView,
    ProfileView,
    RegisterView,
    ResendVerificationView,
    UpdateDefaultLicenseView,
    VerifyEmailView,
)

app_name = "users"

urlpatterns = [
    path("login/", LoginView.as_view(), name="login"),
    path("register/", RegisterView.as_view(), name="register"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("profile/", ProfileView.as_view(), name="profile"),
    path("profile/change-username/", ChangeUsernameView.as_view(), name="change_username"),
    path("profile/change-password/", ChangePasswordView.as_view(), name="change_password"),
    path("profile/update-default-license/", UpdateDefaultLicenseView.as_view(), name="update_default_license"),
    path("profile/delete-account/", DeleteAccountView.as_view(), name="delete_account"),
    path("password-reset/", PasswordResetRequestView.as_view(), name="password_reset"),
    path("verify-email/<str:key>/", VerifyEmailView.as_view(), name="verify_email"),
    path("resend-verification/", ResendVerificationView.as_view(), name="resend_verification"),
]
