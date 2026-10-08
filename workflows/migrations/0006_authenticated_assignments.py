from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def remove_fake_links(apps, schema_editor):
    apps.get_model("workflows", "BlockResponse").objects.using(schema_editor.connection.alias).all().delete()
    apps.get_model("workflows", "ShareLink").objects.using(schema_editor.connection.alias).all().delete()
    # Flush deferred foreign-key checks before changing the affected tables.
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("SET CONSTRAINTS ALL IMMEDIATE")


class Migration(migrations.Migration):
    dependencies = [("workflows", "0005_checklist_item_markdown"), ("accounts", "0002_user_role")]
    operations = [
        migrations.RunPython(remove_fake_links, migrations.RunPython.noop),
        migrations.RenameModel(old_name="ShareLink", new_name="TemplateAssignment"),
        migrations.RemoveField(model_name="templateassignment", name="token"),
        migrations.RemoveField(model_name="templateassignment", name="name"),
        migrations.AddField(model_name="templateassignment", name="user", field=models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.CASCADE, related_name="template_assignments", verbose_name="utente", limit_choices_to={"role": "user"})),
        migrations.AlterField(model_name="templateassignment", name="template", field=models.ForeignKey(to="workflows.template", on_delete=django.db.models.deletion.CASCADE, related_name="assignments", verbose_name="template")),
        migrations.AlterField(model_name="templateassignment", name="created_by", field=models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.PROTECT, related_name="created_assignments", verbose_name="assegnato da")),
        migrations.AlterField(model_name="templateassignment", name="created_at", field=models.DateTimeField(auto_now_add=True, verbose_name="assegnato il")),
        migrations.AddConstraint(model_name="templateassignment", constraint=models.UniqueConstraint(fields=("template", "user"), name="unique_template_user_assignment")),
        migrations.RemoveConstraint(model_name="blockresponse", name="unique_response_per_link_block"),
        migrations.RenameField(model_name="blockresponse", old_name="link", new_name="assignment"),
        migrations.AlterField(model_name="blockresponse", name="assignment", field=models.ForeignKey(to="workflows.templateassignment", on_delete=django.db.models.deletion.CASCADE, related_name="responses", verbose_name="assegnazione")),
        migrations.AddConstraint(model_name="blockresponse", constraint=models.UniqueConstraint(fields=("assignment", "block"), name="unique_response_per_assignment_block")),
    ]
