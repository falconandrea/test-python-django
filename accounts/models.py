from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        MODERATOR = "moderator", "Moderatore"
        USER = "user", "User"

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.USER,
    )

    def save(self, *args, **kwargs):
        if self.is_superuser:
            self.role = self.Role.ADMIN
        self.is_staff = self.is_superuser or self.role in (self.Role.ADMIN, self.Role.MODERATOR)
        if kwargs.get("update_fields") is not None:
            kwargs["update_fields"] = set(kwargs["update_fields"]) | {"is_staff", "role"}
        super().save(*args, **kwargs)

    @property
    def is_admin(self):
        return self.is_superuser or self.role == self.Role.ADMIN
