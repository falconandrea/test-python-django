from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("workflows", "0006_authenticated_assignments")]
    operations = [
        migrations.AlterField(
            model_name="block",
            name="content",
            field=models.TextField(blank=True, verbose_name="contenuto", help_text="Testo Markdown del blocco, mostrato anche sopra checklist e campi di testo."),
        ),
    ]
