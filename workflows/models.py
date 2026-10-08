import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone



class Template(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Bozza"
        CONFIRMED = "confirmed", "Confermato"

    name = models.CharField("nome", max_length=200)
    status = models.CharField(
        "stato", max_length=20, choices=Status.choices, default=Status.DRAFT
    )
    moderators = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        verbose_name="moderatori",
        related_name="assigned_templates",
        blank=True,
        limit_choices_to={"role": "moderator"},
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="creato da",
        related_name="created_templates",
        on_delete=models.PROTECT,
    )
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="confermato da",
        related_name="confirmed_templates",
        on_delete=models.PROTECT,
        blank=True,
        null=True,
    )
    confirmed_at = models.DateTimeField("confermato il", blank=True, null=True)
    duplicated_from = models.ForeignKey(
        "self",
        verbose_name="duplicato da",
        related_name="duplicates",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField("creato il", auto_now_add=True)
    updated_at = models.DateTimeField("modificato il", auto_now=True)

    class Meta:
        ordering = ("name",)
        verbose_name = "template"
        verbose_name_plural = "template"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.pk and Template.objects.filter(pk=self.pk, status=self.Status.CONFIRMED).exists():
            raise ValidationError("Un template confermato non si può modificare.")
        super().save(*args, **kwargs)

    @property
    def is_confirmed(self):
        return self.status == self.Status.CONFIRMED

    def confirm(self, user):
        if self.is_confirmed:
            return
        if not self.blocks.exists():
            raise ValidationError("Aggiungi almeno un blocco prima di confermare il template.")
        self.status = self.Status.CONFIRMED
        self.confirmed_by = user
        self.confirmed_at = timezone.now()
        self.save(update_fields=("status", "confirmed_by", "confirmed_at", "updated_at"))

    def duplicate(self, user):
        copy = Template.objects.create(
            name=f"{self.name} (copia)",
            created_by=user,
            duplicated_from=self,
        )
        copy.moderators.set(self.moderators.all())
        for block in self.blocks.order_by("position"):
            copied_block = Block.objects.create(
                template=copy,
                title=block.title,
                kind=block.kind,
                position=block.position,
                content=block.content,
                required=block.required,
            )
            ChecklistItem.objects.bulk_create(
                [
                    ChecklistItem(
                        block=copied_block,
                        label=item.label,
                        position=item.position,
                    )
                    for item in block.checklist_items.order_by("position")
                ]
            )
        return copy


class Block(models.Model):
    class Kind(models.TextChoices):
        RICH_TEXT = "rich_text", "Testo formattato"
        CHECKLIST = "checklist", "Checklist"
        TEXTAREA = "textarea", "Campo di testo"

    template = models.ForeignKey(
        Template, verbose_name="template", related_name="blocks", on_delete=models.CASCADE
    )
    title = models.CharField("titolo", max_length=200)
    kind = models.CharField("tipo", max_length=20, choices=Kind.choices)
    position = models.PositiveIntegerField("ordine", default=0)
    content = models.TextField(
        "contenuto",
        blank=True,
        help_text="Testo formattato del blocco. Per checklist e textarea resta vuoto.",
    )
    required = models.BooleanField("obbligatorio", default=False)

    class Meta:
        ordering = ("position", "id")
        verbose_name = "blocco"
        verbose_name_plural = "blocchi"

    def __str__(self):
        return f"{self.template.name} · {self.title}"

    def clean(self):
        if self.template_id and self.template.is_confirmed:
            raise ValidationError("I blocchi di un template confermato non si possono modificare.")

    def save(self, *args, **kwargs):
        if self.template_id and self.template.is_confirmed:
            raise ValidationError("I blocchi di un template confermato non si possono modificare.")
        if self.kind != self.Kind.RICH_TEXT:
            self.content = ""
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.template.is_confirmed:
            raise ValidationError("I blocchi di un template confermato non si possono eliminare.")
        return super().delete(*args, **kwargs)


class ChecklistItem(models.Model):
    block = models.ForeignKey(
        Block,
        verbose_name="blocco",
        related_name="checklist_items",
        on_delete=models.CASCADE,
    )
    label = models.TextField("testo Markdown")
    position = models.PositiveIntegerField("ordine", default=0)

    class Meta:
        ordering = ("position", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("block", "position"), name="unique_checklist_item_position_per_block"
            )
        ]
        verbose_name = "voce checklist"
        verbose_name_plural = "voci checklist"

    def __str__(self):
        return self.label

    def clean(self):
        if self.block_id and self.block.template.is_confirmed:
            raise ValidationError("La checklist di un template confermato non si può modificare.")
        if self.block_id and self.block.kind != Block.Kind.CHECKLIST:
            raise ValidationError("Le voci si possono aggiungere solo a un blocco checklist.")

    def save(self, *args, **kwargs):
        if self.block_id and self.block.template.is_confirmed:
            raise ValidationError("La checklist di un template confermato non si può modificare.")
        if self.block_id and self.block.kind != Block.Kind.CHECKLIST:
            raise ValidationError("Le voci si possono aggiungere solo a un blocco checklist.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.block.template.is_confirmed:
            raise ValidationError("La checklist di un template confermato non si può modificare.")
        return super().delete(*args, **kwargs)


class ShareLink(models.Model):
    template = models.ForeignKey(
        Template, verbose_name="template", related_name="share_links", on_delete=models.CASCADE
    )
    name = models.CharField("nome utente", max_length=200)
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="creato da",
        related_name="created_share_links",
        on_delete=models.PROTECT,
    )
    is_active = models.BooleanField("attivo", default=True)
    created_at = models.DateTimeField("creato il", auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "compilazione"
        verbose_name_plural = "risposte"

    def __str__(self):
        return f"{self.name} · {self.template.name}"

    def clean(self):
        if self.template_id and not self.template.is_confirmed:
            raise ValidationError("Puoi creare link solo per template confermati.")


class BlockResponse(models.Model):
    link = models.ForeignKey(
        ShareLink, verbose_name="link", related_name="responses", on_delete=models.CASCADE
    )
    block = models.ForeignKey(
        Block, verbose_name="blocco", related_name="responses", on_delete=models.CASCADE
    )
    text_value = models.TextField("risposta", blank=True)
    checked_items = models.ManyToManyField(
        ChecklistItem, verbose_name="voci selezionate", related_name="responses", blank=True
    )
    updated_at = models.DateTimeField("modificato il", auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("link", "block"), name="unique_response_per_link_block")
        ]
        verbose_name = "risposta"
        verbose_name_plural = "risposte"

    def clean(self):
        if self.link_id and self.block_id and self.link.template_id != self.block.template_id:
            raise ValidationError("La risposta deve riferirsi a un blocco del template del link.")
