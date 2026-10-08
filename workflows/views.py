from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from .models import Block, BlockResponse, ChecklistItem, ShareLink


def public_block_rows(blocks, responses, request=None):
    rows = []
    for block in blocks:
        response = responses.get(block.pk)
        if request is not None and block.kind == Block.Kind.TEXTAREA:
            text_value = request.POST.get(f"text_{block.pk}", "")
        else:
            text_value = response.text_value if response else ""
        if request is not None and block.kind == Block.Kind.CHECKLIST:
            checked_ids = set(request.POST.getlist(f"checklist_{block.pk}"))
        elif response:
            checked_ids = {str(item.pk) for item in response.checked_items.all()}
        else:
            checked_ids = set()
        rows.append(
            {
                "block": block,
                "text_value": text_value,
                "checked_ids": checked_ids,
            }
        )
    return rows


@require_http_methods(["GET", "POST"])
def public_form(request, token):
    link = get_object_or_404(
        ShareLink.objects.select_related("template").prefetch_related(
            "template__blocks__checklist_items", "responses__checked_items"
        ),
        token=token,
    )
    if not link.is_active:
        return render(request, "workflows/link_closed.html", status=410)
    if not link.template.is_confirmed:
        raise Http404

    blocks = list(
        link.template.blocks.prefetch_related("checklist_items").order_by("position", "pk")
    )
    responses = {
        response.block_id: response
        for response in link.responses.prefetch_related("checked_items")
    }

    if request.method == "POST":
        pending = []
        errors = []
        for block in blocks:
            if block.kind == Block.Kind.TEXTAREA:
                value = request.POST.get(f"text_{block.pk}", "").strip()
                if block.required and not value:
                    errors.append(f'Il campo "{block.title}" è obbligatorio.')
                pending.append((block, value, []))
            elif block.kind == Block.Kind.CHECKLIST:
                submitted_ids = request.POST.getlist(f"checklist_{block.pk}")
                allowed_ids = {str(item.pk) for item in block.checklist_items.all()}
                selected_ids = set(submitted_ids) & allowed_ids
                if block.required and not selected_ids:
                    errors.append(f'Seleziona almeno una voce in "{block.title}".')
                pending.append((block, "", selected_ids))

        if errors:
            return render(
                request,
                "workflows/public_form.html",
                {
                    "link": link,
                    "template": link.template,
                    "block_rows": public_block_rows(blocks, responses, request),
                    "errors": errors,
                },
                status=400,
            )

        try:
            with transaction.atomic():
                for block, value, selected_ids in pending:
                    response, _ = BlockResponse.objects.get_or_create(link=link, block=block)
                    response.text_value = value
                    response.full_clean()
                    response.save(update_fields=("text_value", "updated_at"))
                    if block.kind == Block.Kind.CHECKLIST:
                        response.checked_items.set(
                            ChecklistItem.objects.filter(block=block, pk__in=selected_ids)
                        )
        except ValidationError as error:
            raise Http404 from error

        messages.success(request, "Le risposte sono state salvate. Puoi riaprire il link per modificarle.")
        return redirect("public-form", token=token)

    return render(
        request,
        "workflows/public_form.html",
        {
            "link": link,
            "template": link.template,
            "block_rows": public_block_rows(blocks, responses),
        },
    )
