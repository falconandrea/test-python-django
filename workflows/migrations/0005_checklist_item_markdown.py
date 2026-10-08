from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("workflows", "0004_block_content_to_markdown")]
    operations = [
        migrations.AlterField(
            model_name="checklistitem",
            name="label",
            field=models.TextField(verbose_name="testo Markdown"),
        ),
    ]
