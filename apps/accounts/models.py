from django.contrib.auth.models import AbstractUser
from django.db import models

from apps.common.models import UUIDModel

from .managers import UserManager


class User(UUIDModel, AbstractUser):
    username = None
    email = models.EmailField(unique=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        return self.email
