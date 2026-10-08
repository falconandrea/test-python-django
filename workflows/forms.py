from django import forms
from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet

from .models import Block, ChecklistItem


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
    checklist_lines = forms.CharField(
        label="Voci checklist",
        required=False,
        help_text="Usato solo per i blocchi checklist: inserisci una voce per riga.",
        widget=forms.Textarea(attrs={"rows": 4, "placeholder": "Prima voce\nSeconda voce"}),
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
            self.fields["checklist_lines"].initial = "\n".join(
                self.instance.checklist_items.order_by("position").values_list("label", flat=True)
            )


class BlockInlineFormSet(BaseInlineFormSet):
    def add_fields(self, form, index):
        super().add_fields(form, index)
        if index is None or index < self.initial_form_count():
            return

        if self.instance.pk:
            latest = (
                Block.objects.filter(template_id=self.instance.pk)
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
        saved_instances = super().save(commit=commit)
        if not commit:
            return saved_instances

        for form in self.forms:
            if not form.cleaned_data or form.cleaned_data.get("DELETE") or not form.has_changed():
                continue
            block = form.instance
            block.checklist_items.all().delete()
            if block.kind == Block.Kind.CHECKLIST:
                labels = [
                    label.strip()
                    for label in form.cleaned_data.get("checklist_lines", "").splitlines()
                    if label.strip()
                ]
                ChecklistItem.objects.bulk_create(
                    [
                        ChecklistItem(block=block, label=label, position=position)
                        for position, label in enumerate(labels)
                    ]
                )
        return saved_instances
