# Licensed under the MIT License.
# See LICENSE file in the project root for full license information.

import random
import string
from uuid import uuid4

from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.db import models
from model_utils.models import TimeStampedModel


def generate_random_name():
    random_digits = "".join(random.choices(string.digits, k=6))
    return "User" + random_digits


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, password=None, **extra_fields):
        """
        Creates and saves a User with the given email and password.
        """
        if not email:
            raise ValueError("The Email must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password, **extra_fields):
        """
        Creates and saves a superuser with the given email and password.
        """
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, password, **extra_fields)


# Create your models here.
class User(AbstractUser, TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)

    # User model only needs email and password. No username is needed.
    username = None
    email = models.EmailField("email address", unique=True)

    name = models.CharField("Name", max_length=255, default=generate_random_name)
    bio = models.CharField("Bio", max_length=10000, default="")

    first_name = None  # type: ignore
    last_name = None  # type: ignore

    # The number of warnings the user has received
    warnings = models.IntegerField(default=0)

    # Additional flag to indicate if user is a volunteer
    is_volunteer = models.BooleanField(default=False)
    # Flag to indicate an expert user. Their votes will provide direct validation
    is_expert = models.BooleanField(
        default=False,
        help_text="Expert user votes directly validate Category, Species and Activity without need for additional consensus",
    )
    # Phone number if needed
    phone_number = models.CharField("Phone Number", max_length=25, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["name"]

    objects = UserManager()

    def __str__(self):
        return f"{self.name}"


class BannedEmail(TimeStampedModel):
    """Track email addresses that have been permanently banned."""

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    email = models.EmailField(unique=True)
    ban_reason = models.TextField(max_length=2000)

    def __str__(self):
        return self.email
