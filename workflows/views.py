from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max
from django.forms import inlineformset_factory
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from .forms import BlockInlineForm, BlockInlineFormSet, TemplateEditorForm, WorkbookEditorForm, WorkbookCreateForm, WorkbookAdminEditorForm
from .models import Block, BlockResponse, ChecklistItem, Template, Workbook, WorkbookAssignment
from .permissions import is_admin_user, can_edit_workbook


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
                "has_response": response is not None,
                "text_value": text_value,
                "checked_ids": checked_ids,
            }
        )
    return rows


@login_required
@require_http_methods(["GET", "POST"])
@transaction.atomic
def public_form(request, pk):
    queryset = WorkbookAssignment.objects.select_related("workbook", "user").prefetch_related("responses__checked_items")
    if request.method == "POST":
        queryset = queryset.select_for_update(of=("self", "workbook"))
    assignment = get_object_or_404(
        queryset,
        workbook_id=pk, user=request.user, user__role="user", is_active=True,
        workbook__status=Workbook.Status.CONFIRMED,
    )
    blocks = list(
        assignment.workbook.blocks.prefetch_related("checklist_items").order_by("position", "pk")
    )
    responses = {
        response.block_id: response
        for response in assignment.responses.prefetch_related("checked_items")
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
                    "assignment": assignment,
                    "workbook": assignment.workbook,
                    "block_rows": public_block_rows(blocks, responses, request),
                    "errors": errors,
                },
                status=400,
            )

        try:
            with transaction.atomic():
                for block, value, selected_ids in pending:
                    response, _ = BlockResponse.objects.get_or_create(assignment=assignment, block=block)
                    response.text_value = value
                    response.full_clean()
                    response.save(update_fields=("text_value", "updated_at"))
                    if block.kind == Block.Kind.CHECKLIST:
                        response.checked_items.set(
                            ChecklistItem.objects.filter(block=block, pk__in=selected_ids)
                        )
        except ValidationError as error:
            raise Http404 from error

        messages.success(request, "Le risposte sono state salvate. Puoi tornare al workbook per modificarle.")
        return redirect("workbook-fill", pk=pk)

    return render(
        request,
        "workflows/public_form.html",
        {
            "assignment": assignment,
            "workbook": assignment.workbook,
            "block_rows": public_block_rows(blocks, responses),
        },
    )


@login_required
def dashboard(request):
    if is_admin_user(request.user):
        workbooks = Workbook.objects.select_related("moderator", "source_template").all()
    elif request.user.role == "moderator":
        workbooks = Workbook.objects.select_related("source_template").filter(moderator=request.user)
    else:
        assignments = request.user.workbook_assignments.filter(is_active=True, workbook__status=Workbook.Status.CONFIRMED).select_related("workbook").annotate(last_update=Max("responses__updated_at"))
        return render(request, "workflows/dashboard.html", {"assignments": assignments})
    context = {"managed_workbooks": workbooks.order_by("name")}
    if is_admin_user(request.user):
        context["templates"] = Template.objects.all()
    return render(request, "workflows/dashboard.html", context)


def managed_workbook(request, pk):
    if is_admin_user(request.user):
        queryset = Workbook.objects.all()
    elif request.user.role == "moderator":
        queryset = Workbook.objects.filter(moderator=request.user)
    else:
        queryset = Workbook.objects.none()
    if request.method == "POST":
        queryset = queryset.select_for_update()
    return get_object_or_404(queryset, pk=pk)


def block_formset(owner_class, data, owner):
    FormSet = inlineformset_factory(owner_class, Block, form=BlockInlineForm, formset=BlockInlineFormSet, fk_name="workbook" if owner_class == Workbook else "template", extra=0, can_delete=True)
    return FormSet(data, instance=owner, prefix="blocks")


@login_required
@require_http_methods(["GET", "POST"])
@transaction.atomic
def template_edit(request, pk):
    if not is_admin_user(request.user):
        raise Http404
    template = get_object_or_404(Template, pk=pk)
    data = request.POST if request.method == "POST" else None
    form = TemplateEditorForm(data, instance=template)
    formset = block_formset(Template, data, template)
    if request.method == "POST":
        valid_form = form.is_valid()
        valid_blocks = formset.is_valid()
        if valid_form and valid_blocks:
            form.save()
            formset.save()
            messages.success(request, "Template salvato. I workbook già creati restano indipendenti.")
            return redirect("template-edit", pk=pk)
    return render(request, "workflows/structure_edit.html", {"entity": template, "form": form, "formset": formset, "is_workbook": False})


@login_required
@require_http_methods(["GET", "POST"])
@transaction.atomic
def workbook_create(request):
    if not is_admin_user(request.user):
        raise Http404
    form = WorkbookCreateForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        workbook = form.save(commit=False)
        workbook.created_by = request.user
        workbook.save()
        form.save_assignments(request.user)
        messages.success(request, "Workbook creato copiando la struttura del template.")
        return redirect("workbook-edit", pk=workbook.pk)
    return render(request, "workflows/workbook_create.html", {"form": form})


@login_required
@require_http_methods(["GET", "POST"])
@transaction.atomic
def workbook_edit(request, pk):
    workbook = managed_workbook(request, pk)
    if not can_edit_workbook(request.user, workbook):
        if request.method == "POST":
            raise Http404
        return render(request, "workflows/workbook_detail.html", {"workbook": workbook})
    data = request.POST if request.method == "POST" else None
    Form = WorkbookAdminEditorForm if is_admin_user(request.user) else WorkbookEditorForm
    form = Form(data, instance=workbook)
    formset = block_formset(Workbook, data, workbook)
    if request.method == "POST":
        valid_form = form.is_valid()
        valid_blocks = formset.is_valid()
        if valid_form and valid_blocks:
            form.save()
            formset.save()
            form.save_assignments(request.user)
            if request.POST.get("action") == "confirm":
                try:
                    workbook.confirm(request.user)
                except ValidationError as error:
                    form.add_error(None, error)
                    transaction.set_rollback(True)
                else:
                    messages.success(request, "Workbook confermato.")
                    return redirect("workbook-edit", pk=pk)
            else:
                messages.success(request, "Workbook salvato.")
                return redirect("workbook-edit", pk=pk)
    return render(request, "workflows/structure_edit.html", {"entity": workbook, "form": form, "formset": formset, "is_workbook": True})


@login_required
@require_http_methods(["GET", "POST"])
@transaction.atomic
def workbook_responses(request, pk):
    workbook = managed_workbook(request, pk)
    form = WorkbookEditorForm(request.POST if request.method == "POST" else None, instance=workbook)
    form.fields.pop("name")
    if request.method == "POST" and form.is_valid():
        form.save_assignments(request.user)
        messages.success(request, "Utenti collegati aggiornati.")
        return redirect("workbook-responses", pk=pk)
    assignments = workbook.assignments.select_related("user").prefetch_related("responses__checked_items")
    blocks = list(workbook.blocks.prefetch_related("checklist_items").all())
    rows = [{"assignment": assignment, "blocks": public_block_rows(blocks, {response.block_id: response for response in assignment.responses.all()})} for assignment in assignments]
    return render(request, "workflows/workbook_responses.html", {"workbook": workbook, "form": form, "rows": rows})
