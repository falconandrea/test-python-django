import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Template",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=200, verbose_name="nome")),
                ("status", models.CharField(choices=[("draft", "Bozza"), ("confirmed", "Confermato")], default="draft", max_length=20, verbose_name="stato")),
                ("confirmed_at", models.DateTimeField(blank=True, null=True, verbose_name="confermato il")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="creato il")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="modificato il")),
                ("confirmed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="confirmed_templates", to=settings.AUTH_USER_MODEL, verbose_name="confermato da")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_templates", to=settings.AUTH_USER_MODEL, verbose_name="creato da")),
                ("duplicated_from", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="duplicates", to="workflows.template", verbose_name="duplicato da")),
                ("moderators", models.ManyToManyField(blank=True, limit_choices_to={"role": "moderator"}, related_name="assigned_templates", to=settings.AUTH_USER_MODEL, verbose_name="moderatori")),
            ],
            options={"verbose_name": "template", "verbose_name_plural": "template", "ordering": ("name",)},
        ),
        migrations.CreateModel(
            name="Block",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=200, verbose_name="titolo")),
                ("kind", models.CharField(choices=[("rich_text", "Testo formattato"), ("checklist", "Checklist"), ("textarea", "Campo di testo")], max_length=20, verbose_name="tipo")),
                ("position", models.PositiveIntegerField(default=0, verbose_name="ordine")),
                ("content", models.TextField(blank=True, help_text="Testo formattato del blocco. Per checklist e textarea resta vuoto.", verbose_name="contenuto")),
                ("required", models.BooleanField(default=False, verbose_name="obbligatorio")),
                ("template", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="blocks", to="workflows.template", verbose_name="template")),
            ],
            options={"verbose_name": "blocco", "verbose_name_plural": "blocchi", "ordering": ("position", "id")},
        ),
        migrations.CreateModel(
            name="ChecklistItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("label", models.CharField(max_length=300, verbose_name="voce")),
                ("position", models.PositiveIntegerField(default=0, verbose_name="ordine")),
                ("block", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="checklist_items", to="workflows.block", verbose_name="blocco")),
            ],
            options={"verbose_name": "voce checklist", "verbose_name_plural": "voci checklist", "ordering": ("position", "id")},
        ),
        migrations.CreateModel(
            name="ShareLink",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=200, verbose_name="nome utente")),
                ("token", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("is_active", models.BooleanField(default=True, verbose_name="attivo")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="creato il")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_share_links", to=settings.AUTH_USER_MODEL, verbose_name="creato da")),
                ("template", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="share_links", to="workflows.template", verbose_name="template")),
            ],
            options={"verbose_name": "link compilazione", "verbose_name_plural": "link compilazione", "ordering": ("-created_at",)},
        ),
        migrations.CreateModel(
            name="BlockResponse",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("text_value", models.TextField(blank=True, verbose_name="risposta")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="modificato il")),
                ("block", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="responses", to="workflows.block", verbose_name="blocco")),
                ("checked_items", models.ManyToManyField(blank=True, related_name="responses", to="workflows.checklistitem", verbose_name="voci selezionate")),
                ("link", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="responses", to="workflows.sharelink", verbose_name="link")),
            ],
            options={"verbose_name": "risposta", "verbose_name_plural": "risposte"},
        ),
        migrations.AddConstraint(
            model_name="block",
            constraint=models.UniqueConstraint(fields=("template", "position"), name="unique_block_position_per_template"),
        ),
        migrations.AddConstraint(
            model_name="checklistitem",
            constraint=models.UniqueConstraint(fields=("block", "position"), name="unique_checklist_item_position_per_block"),
        ),
        migrations.AddConstraint(
            model_name="blockresponse",
            constraint=models.UniqueConstraint(fields=("link", "block"), name="unique_response_per_link_block"),
        ),
    ]
