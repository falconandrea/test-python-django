from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("workflows", "0002_django_admin_backoffice"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="sharelink",
            options={
                "ordering": ("-created_at",),
                "verbose_name": "compilazione",
                "verbose_name_plural": "risposte",
            },
        ),
    ]
