from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone


class Template(models.Model):
    name = models.CharField("nome", max_length=200)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="creato da", related_name="created_templates", on_delete=models.PROTECT)
    duplicated_from = models.ForeignKey("self", verbose_name="duplicato da", related_name="duplicates", on_delete=models.SET_NULL, blank=True, null=True)
    created_at = models.DateTimeField("creato il", auto_now_add=True)
    updated_at = models.DateTimeField("modificato il", auto_now=True)

    class Meta:
        ordering = ("name",)
        verbose_name = "template"
        verbose_name_plural = "template"

    def __str__(self):
        return self.name

    @transaction.atomic
    def copy_blocks_to(self, destination):
        # Serialize copying with edits that save the template before its blocks.
        type(self).objects.select_for_update().get(pk=self.pk)
        owner = {"workbook": destination} if isinstance(destination, Workbook) else {"template": destination}
        for block in self.blocks.prefetch_related("checklist_items").all():
            copied = Block.objects.create(**owner, title=block.title, kind=block.kind, position=block.position, content=block.content, required=block.required)
            ChecklistItem.objects.bulk_create([
                ChecklistItem(block=copied, label=item.label, position=item.position)
                for item in block.checklist_items.all()
            ])

    @transaction.atomic
    def duplicate(self, user):
        copy = Template.objects.create(name=f"{self.name} (copia)", created_by=user, duplicated_from=self)
        self.copy_blocks_to(copy)
        return copy


class Workbook(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Bozza"
        CONFIRMED = "confirmed", "Confermato"

    name = models.CharField("nome", max_length=200)
    source_template = models.ForeignKey(Template, verbose_name="template di origine", related_name="workbooks", on_delete=models.PROTECT)
    moderator = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="moderatore", related_name="moderated_workbooks", on_delete=models.PROTECT, limit_choices_to={"role": "moderator"})
    status = models.CharField("stato", max_length=20, choices=Status.choices, default=Status.DRAFT)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="creato da", related_name="created_workbooks", on_delete=models.PROTECT)
    confirmed_by = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="confermato da", related_name="confirmed_workbooks", on_delete=models.PROTECT, blank=True, null=True)
    confirmed_at = models.DateTimeField("confermato il", blank=True, null=True)
    created_at = models.DateTimeField("creato il", auto_now_add=True)
    updated_at = models.DateTimeField("modificato il", auto_now=True)

    class Meta:
        ordering = ("name",)
        verbose_name = "workbook"
        verbose_name_plural = "workbook"

    def __str__(self):
        return self.name

    @transaction.atomic
    def save(self, *args, **kwargs):
        creating = self._state.adding
        if not creating:
            original_source = type(self).objects.filter(pk=self.pk).values_list("source_template_id", flat=True).first()
            if original_source != self.source_template_id:
                raise ValidationError("Il template di origine di un workbook non può essere cambiato.")
        super().save(*args, **kwargs)
        if creating:
            self.source_template.copy_blocks_to(self)

    @property
    def is_confirmed(self):
        return self.status == self.Status.CONFIRMED

    def clean(self):
        if self.moderator_id and self.moderator.role != "moderator":
            raise ValidationError("Scegli un utente con ruolo moderatore.")

    def confirm(self, user):
        from .permissions import can_manage_workbook
        if not can_manage_workbook(user, self):
            raise ValidationError("Non puoi confermare questo workbook.")
        if self.is_confirmed:
            return
        if not self.blocks.exists():
            raise ValidationError("Aggiungi almeno un blocco prima di confermare il workbook.")
        self.status = self.Status.CONFIRMED
        self.confirmed_by = user
        self.confirmed_at = timezone.now()
        self.save(update_fields=("status", "confirmed_by", "confirmed_at", "updated_at"))


class Block(models.Model):
    class Kind(models.TextChoices):
        RICH_TEXT = "rich_text", "Testo formattato"
        CHECKLIST = "checklist", "Checklist"
        TEXTAREA = "textarea", "Campo di testo"

    template = models.ForeignKey(Template, verbose_name="template", related_name="blocks", on_delete=models.CASCADE, blank=True, null=True)
    workbook = models.ForeignKey(Workbook, verbose_name="workbook", related_name="blocks", on_delete=models.CASCADE, blank=True, null=True)
    title = models.CharField("titolo", max_length=200)
    kind = models.CharField("tipo", max_length=20, choices=Kind.choices)
    position = models.PositiveIntegerField("ordine", default=0)
    content = models.TextField("contenuto", blank=True, help_text="Testo Markdown del blocco, mostrato anche sopra checklist e campi di testo.")
    required = models.BooleanField("obbligatorio", default=False)

    class Meta:
        ordering = ("position", "id")
        verbose_name = "blocco"
        verbose_name_plural = "blocchi"
        constraints = [models.CheckConstraint(condition=(models.Q(template__isnull=False, workbook__isnull=True) | models.Q(template__isnull=True, workbook__isnull=False)), name="block_has_one_owner")]

    def __str__(self):
        return f"{self.template or self.workbook} · {self.title}"

    def clean(self):
        if bool(self.template_id) == bool(self.workbook_id):
            raise ValidationError("Il blocco deve appartenere a un template oppure a un workbook.")


class ChecklistItem(models.Model):
    block = models.ForeignKey(Block, verbose_name="blocco", related_name="checklist_items", on_delete=models.CASCADE)
    label = models.TextField("testo Markdown")
    position = models.PositiveIntegerField("ordine", default=0)

    class Meta:
        ordering = ("position", "id")
        constraints = [models.UniqueConstraint(fields=("block", "position"), name="unique_checklist_item_position_per_block")]
        verbose_name = "voce checklist"
        verbose_name_plural = "voci checklist"

    def __str__(self):
        return self.label

    def clean(self):
        if self.block_id and self.block.kind != Block.Kind.CHECKLIST:
            raise ValidationError("Le voci si possono aggiungere solo a un blocco checklist.")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


class WorkbookAssignment(models.Model):
    workbook = models.ForeignKey(Workbook, verbose_name="workbook", related_name="assignments", on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="utente", related_name="workbook_assignments", on_delete=models.CASCADE, limit_choices_to={"role": "user"})
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="assegnato da", related_name="created_assignments", on_delete=models.PROTECT)
    is_active = models.BooleanField("attivo", default=True)
    created_at = models.DateTimeField("assegnato il", auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "compilazione"
        verbose_name_plural = "risposte"
        constraints = [models.UniqueConstraint(fields=("workbook", "user"), name="unique_workbook_user_assignment")]

    def __str__(self):
        return f"{self.user.username} · {self.workbook.name}"

    def clean(self):
        if self.user_id and self.user.role != "user":
            raise ValidationError("Assegna la compilazione a un utente con ruolo user.")


class BlockResponse(models.Model):
    assignment = models.ForeignKey(WorkbookAssignment, verbose_name="assegnazione", related_name="responses", on_delete=models.CASCADE)
    block = models.ForeignKey(Block, verbose_name="blocco", related_name="responses", on_delete=models.CASCADE)
    text_value = models.TextField("risposta", blank=True)
    checked_items = models.ManyToManyField(ChecklistItem, verbose_name="voci selezionate", related_name="responses", blank=True)
    updated_at = models.DateTimeField("modificato il", auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("assignment", "block"), name="unique_response_per_assignment_block")]
        verbose_name = "risposta"
        verbose_name_plural = "risposte"

    def clean(self):
        if self.assignment_id and self.block_id and self.assignment.workbook_id != self.block.workbook_id:
            raise ValidationError("La risposta deve riferirsi a un blocco del workbook assegnato.")
