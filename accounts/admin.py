from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    fieldsets = DjangoUserAdmin.fieldsets + (("Ruolo applicazione", {"fields": ("role",)}),)
    add_fieldsets = DjangoUserAdmin.add_fieldsets + (("Ruolo applicazione", {"fields": ("role",)}),)
    list_display = (*DjangoUserAdmin.list_display, "role")

    def has_module_permission(self, request):
        return bool(
            request.user.is_authenticated
            and request.user.is_staff
            and (request.user.is_superuser or request.user.is_admin)
        )

    def has_view_permission(self, request, obj=None):
        if not self.has_module_permission(request):
            return False
        return obj is None or request.user.is_superuser or obj.role == User.Role.MODERATOR

    def has_add_permission(self, request):
        return self.has_module_permission(request)

    def has_change_permission(self, request, obj=None):
        if not self.has_module_permission(request):
            return False
        return obj is None or request.user.is_superuser or obj.role == User.Role.MODERATOR

    def has_delete_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if request.user.is_superuser:
            return queryset
        return queryset.filter(role=User.Role.MODERATOR)

    def get_fieldsets(self, request, obj=None):
        if request.user.is_superuser:
            return super().get_fieldsets(request, obj)
        if obj is None:
            return self.add_fieldsets
        return (
            (None, {"fields": ("username", "password")}),
            ("Informazioni", {"fields": ("first_name", "last_name", "email", "role", "is_active")}),
        )

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if not request.user.is_superuser and "role" in form.base_fields:
            form.base_fields["role"].choices = ((User.Role.MODERATOR, "Moderatore"),)
            form.base_fields["role"].initial = User.Role.MODERATOR
        return form

    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser:
            obj.role = User.Role.MODERATOR
            obj.is_superuser = False
        obj.is_staff = True
        super().save_model(request, obj, form, change)
