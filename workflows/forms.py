from django import forms
from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet
from django.db import transaction

from .models import Block, ChecklistItem, Template, Workbook, WorkbookAssignment
from django.contrib.auth import get_user_model


class ChecklistOptionsWidget(forms.HiddenInput):
    is_hidden = False
    template_name = "workflows/widgets/checklist_options.html"

    class Media:
        js = ("workflows/checklist-editor.js",)
        css = {"all": ("workflows/checklist-editor.css",)}


class BlockInlineForm(forms.ModelForm):
    content = forms.CharField(
        label="Testo Markdown",
        required=False,
        help_text="Esempi: # titolo, **grassetto**, *corsivo*, - elenco, [testo](https://indirizzo).",
        widget=forms.Textarea(
            attrs={
                "rows": 6,
                "placeholder": "# Titolo\n\nTesto in **grassetto**\n\n- Prima voce\n- Seconda voce",
            }
        ),
    )
    checklist_options = forms.JSONField(
        label="Opzioni checklist",
        required=False,
        help_text="Aggiungi un'opzione per ogni checkbox. Ogni testo supporta Markdown e più paragrafi.",
        widget=ChecklistOptionsWidget,
    )

    class Meta:
        model = Block
        fields = ("position", "title", "kind", "content", "required")
        labels = {
            "position": "Ordine",
            "title": "Titolo",
            "kind": "Tipo",
            "content": "Testo Markdown",
            "required": "Richiedi una risposta",
        }
        help_texts = {
            "position": "Numero più basso = blocco mostrato prima. Usa un numero diverso per ogni blocco.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and self.instance.kind == Block.Kind.CHECKLIST:
            self.fields["checklist_options"].initial = [
                {"id": item.pk, "text": item.label}
                for item in self.instance.checklist_items.order_by("position")
            ]

    def clean_checklist_options(self):
        options = self.cleaned_data.get("checklist_options") or []
        if not isinstance(options, list):
            raise ValidationError("Le opzioni devono essere una lista.")
        allowed_ids = set(self.instance.checklist_items.values_list("pk", flat=True)) if self.instance.pk else set()
        seen = set()
        cleaned = []
        for option in options:
            if not isinstance(option, dict) or not isinstance(option.get("text"), str):
                raise ValidationError("Ogni opzione deve contenere un testo Markdown.")
            item_id = option.get("id")
            if item_id is not None:
                if type(item_id) is not int or item_id not in allowed_ids or item_id in seen:
                    raise ValidationError("Opzione non valida per questo blocco.")
                seen.add(item_id)
            text = option["text"].strip()
            if not text:
                raise ValidationError("Scrivi il testo di ogni opzione oppure eliminala.")
            cleaned.append({"id": item_id, "text": text})
        return cleaned

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("kind") == Block.Kind.CHECKLIST and not cleaned.get("checklist_options") and "checklist_options" not in self.errors:
            self.add_error("checklist_options", "Aggiungi almeno un'opzione alla checklist.")
        return cleaned



class BlockInlineFormSet(BaseInlineFormSet):
    def add_fields(self, form, index):
        super().add_fields(form, index)
        if index is None or index < self.initial_form_count():
            return

        if self.instance.pk:
            latest = (
                self.instance.blocks.all()
                .order_by("-position")
                .values_list("position", flat=True)
                .first()
            )
        else:
            latest = None
        form.fields["position"].initial = (latest if latest is not None else -1) + 1 + (
            index - self.initial_form_count()
        )

    def clean(self):
        super().clean()
        if any(self.errors):
            return

        positions = set()
        for form in self.forms:
            if not form.cleaned_data or form.cleaned_data.get("DELETE"):
                continue
            if form.empty_permitted and not form.has_changed():
                continue
            position = form.cleaned_data.get("position")
            if position in positions:
                raise ValidationError("Assegna un numero d'ordine diverso a ogni blocco.")
            positions.add(position)

    def save(self, commit=True):
        if not commit:
            return super().save(commit=False)
        with transaction.atomic():
            saved_instances = super().save(commit=True)
            for form in self.forms:
                if not form.cleaned_data or form.cleaned_data.get("DELETE") or not form.has_changed():
                    continue
                block = form.instance
                options = form.cleaned_data.get("checklist_options", []) if block.kind == Block.Kind.CHECKLIST else []
                retained = [option["id"] for option in options if option["id"] is not None]
                block.checklist_items.exclude(pk__in=retained).delete()
                existing = {item.pk: item for item in block.checklist_items.all()}
                offset = max((item.position for item in existing.values()), default=0) + len(options) + 1
                for index, item in enumerate(existing.values()):
                    item.position = offset + index
                    item.save(update_fields=("position",))
                for position, option in enumerate(options):
                    item = existing.get(option["id"]) or ChecklistItem(block=block)
                    item.label = option["text"]
                    item.position = position
                    item.save()
            return saved_instances


class TemplateEditorForm(forms.ModelForm):
    class Meta:
        model = Template
        fields = ("name",)


class WorkbookEditorForm(forms.ModelForm):
    users = forms.ModelMultipleChoiceField(
        label="Utenti che possono rispondere", queryset=get_user_model().objects.none(), required=False,
        widget=forms.SelectMultiple(attrs={"size": 8}),
        help_text="Seleziona gli utenti con ruolo user. Rimuovere un utente revoca l'accesso e conserva le sue risposte.",
    )

    class Meta:
        model = Workbook
        fields = ("name",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["users"].queryset = get_user_model().objects.filter(role="user", is_active=True, is_superuser=False).order_by("username")
        if self.instance.pk:
            self.fields["users"].initial = self.instance.assignments.filter(is_active=True).values_list("user_id", flat=True)

    def save_assignments(self, actor):
        users = self.cleaned_data["users"]
        self.instance.assignments.exclude(user__in=users).update(is_active=False)
        for user in users:
            WorkbookAssignment.objects.update_or_create(workbook=self.instance, user=user, defaults={"is_active": True}, create_defaults={"is_active": True, "created_by": actor})


class WorkbookCreateForm(WorkbookEditorForm):
    class Meta:
        model = Workbook
        fields = ("name", "source_template", "moderator")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "moderator" in self.fields:
            self.fields["moderator"].queryset = get_user_model().objects.filter(role="moderator", is_active=True, is_superuser=False).order_by("username")


class WorkbookAdminEditorForm(WorkbookCreateForm):
    class Meta:
        model = Workbook
        fields = ("name", "moderator")
