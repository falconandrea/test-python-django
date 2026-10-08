from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        MODERATOR = "moderator", "Moderatore"

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.MODERATOR,
    )

    @property
    def is_admin(self):
        return self.is_superuser or self.role == self.Role.ADMIN
