from django.db import migrations


def enable_admin_login_for_staff_roles(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    User.objects.filter(role__in=("admin", "moderator")).update(is_staff=True)


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
        ("workflows", "0001_initial"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="block",
            name="unique_block_position_per_template",
        ),
        migrations.RunPython(enable_admin_login_for_staff_roles, migrations.RunPython.noop),
    ]
