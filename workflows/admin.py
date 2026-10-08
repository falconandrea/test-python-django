from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.db.models import Count, Max
from django.utils.html import format_html, format_html_join

from .forms import BlockInlineForm, BlockInlineFormSet, WorkbookCreateForm
from .models import Block, Template, Workbook, WorkbookAssignment
from .permissions import is_admin_user, can_manage_workbook, can_edit_workbook
from .utils import render_markdown


class BlockInline(admin.TabularInline):
    model = Block
    fk_name = "template"
    form = BlockInlineForm
    formset = BlockInlineFormSet
    fields = ("position", "title", "kind", "content", "checklist_options", "required")
    ordering = ("position", "pk")
    extra = 1

    def checklist_options(self, obj):
        return format_html_join("", "<div>{}</div>", ((render_markdown(item.label),) for item in obj.checklist_items.all()))

    def has_view_permission(self, request, obj=None):
        return is_admin_user(request.user)

    def has_add_permission(self, request, obj=None):
        return self.has_change_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        return is_admin_user(request.user)

    def has_delete_permission(self, request, obj=None):
        return self.has_change_permission(request, obj)


class WorkbookBlockInline(BlockInline):
    fk_name = "workbook"

    def has_view_permission(self, request, obj=None):
        if is_admin_user(request.user):
            return True
        if not request.user.is_authenticated or request.user.role != "moderator":
            return False
        # Django also checks this permission without the parent when building the queryset.
        return obj is None or can_manage_workbook(request.user, obj)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if is_admin_user(request.user):
            return queryset
        return queryset.filter(workbook__moderator=request.user)

    def has_change_permission(self, request, obj=None):
        return is_admin_user(request.user) or (obj is not None and can_edit_workbook(request.user, obj))

    def get_readonly_fields(self, request, obj=None):
        return () if self.has_change_permission(request, obj) else self.fields


@admin.register(Template)
class TemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "block_count", "created_by", "updated_at")
    search_fields = ("name",)
    list_select_related = ("created_by",)
    inlines = (BlockInline,)
    fields = ("name", "created_by", "created_at", "updated_at", "duplicated_from")
    readonly_fields = ("created_by", "created_at", "updated_at", "duplicated_from")
    actions = ("duplicate_selected",)

    def has_module_permission(self, request):
        return is_admin_user(request.user)

    def has_view_permission(self, request, obj=None):
        return is_admin_user(request.user)

    def has_add_permission(self, request):
        return is_admin_user(request.user)

    def has_change_permission(self, request, obj=None):
        return is_admin_user(request.user)

    def has_delete_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_block_count=Count("blocks", distinct=True))

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    @admin.display(description="Blocchi", ordering="_block_count")
    def block_count(self, obj):
        return obj._block_count

    @admin.action(description="Duplica i template selezionati", permissions=("change",))
    def duplicate_selected(self, request, queryset):
        copies = [template.duplicate(request.user) for template in queryset]
        self.message_user(request, f"Create {len(copies)} copie.", level=messages.SUCCESS)


@admin.register(Workbook)
class WorkbookAdmin(admin.ModelAdmin):
    form = WorkbookCreateForm
    list_display = ("name", "source_template", "moderator", "status", "created_by")
    list_filter = ("status", "moderator", "source_template")
    search_fields = ("name", "source_template__name", "moderator__username")
    list_select_related = ("source_template", "moderator", "created_by")
    inlines = (WorkbookBlockInline,)
    fields = ("name", "source_template", "moderator", "users", "status", "created_by", "created_at", "updated_at", "confirmed_by", "confirmed_at")
    readonly_fields = ("status", "created_by", "created_at", "updated_at", "confirmed_by", "confirmed_at")
    actions = ("confirm_selected",)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset if is_admin_user(request.user) else queryset.filter(moderator=request.user)

    def has_module_permission(self, request):
        return request.user.is_authenticated and (is_admin_user(request.user) or request.user.role == "moderator")

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request) and (obj is None or can_manage_workbook(request.user, obj))

    def has_change_permission(self, request, obj=None):
        # Anche a conferma avvenuta il moderatore gestisce gli utenti collegati.
        return self.has_view_permission(request, obj)

    def has_add_permission(self, request):
        return is_admin_user(request.user)

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        readonly = list(self.readonly_fields)
        if obj:
            readonly.append("source_template")
        if not is_admin_user(request.user):
            readonly.append("moderator")
            if obj and obj.is_confirmed:
                readonly.append("name")
        return tuple(readonly)

    def get_inline_instances(self, request, obj=None):
        # La creazione copia i blocchi del template; l'editor si usa dopo il salvataggio.
        return super().get_inline_instances(request, obj) if obj else []

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        form.save_assignments(request.user)

    @admin.action(description="Conferma i workbook selezionati", permissions=("change",))
    def confirm_selected(self, request, queryset):
        confirmed = 0
        for workbook in queryset.filter(status=Workbook.Status.DRAFT):
            try:
                workbook.confirm(request.user)
            except ValidationError as error:
                self.message_user(request, f'"{workbook.name}": {" ".join(error.messages)}', level=messages.ERROR)
            else:
                confirmed += 1
        if confirmed:
            self.message_user(request, f"Confermati {confirmed} workbook.", level=messages.SUCCESS)


@admin.register(WorkbookAssignment)
class WorkbookAssignmentAdmin(admin.ModelAdmin):
    list_display = ("user", "workbook", "is_active", "last_response_update", "created_at")
    list_filter = ("is_active", "workbook")
    search_fields = ("user__username", "workbook__name")
    fields = ("workbook", "user", "is_active", "answers_summary", "created_by", "created_at")
    readonly_fields = fields

    def get_queryset(self, request):
        queryset = super().get_queryset(request).select_related("workbook", "user", "created_by").annotate(_last_response_update=Max("responses__updated_at")).prefetch_related("workbook__blocks__checklist_items", "responses__checked_items")
        return queryset if is_admin_user(request.user) else queryset.filter(workbook__moderator=request.user)

    def has_module_permission(self, request):
        return request.user.is_authenticated and (is_admin_user(request.user) or request.user.role == "moderator")

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request) and (obj is None or can_manage_workbook(request.user, obj.workbook))

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="Ultima risposta", ordering="_last_response_update", empty_value="—")
    def last_response_update(self, obj):
        return obj._last_response_update

    @admin.display(description="Risposte della persona")
    def answers_summary(self, obj):
        responses = {response.block_id: response for response in obj.responses.all()}
        sections = []

        for block in obj.workbook.blocks.all():
            if block.kind == Block.Kind.RICH_TEXT:
                continue

            response = responses.get(block.pk)
            if block.kind == Block.Kind.CHECKLIST:
                if response is None:
                    body = format_html("<p>{}</p>", "Non ancora compilata")
                else:
                    selected_items = response.checked_items.all()
                    if selected_items:
                        items = format_html_join("", "<li>{}</li>", ((render_markdown(item.label),) for item in selected_items))
                        body = format_html("<ul>{}</ul>", items)
                    else:
                        body = format_html("<p>{}</p>", "Nessuna voce selezionata")
            elif response is None:
                body = format_html("<p>{}</p>", "Non ancora compilato")
            elif response.text_value:
                body = format_html('<div style="white-space: pre-wrap">{}</div>', response.text_value)
            else:
                body = format_html("<p>{}</p>", "Nessuna risposta")

            sections.append(
                format_html(
                    '<section style="margin: 0 0 1.25rem; padding-bottom: 1rem; border-bottom: 1px solid #ddd;">'
                    "<h3 style=\"margin-bottom: .4rem\">{}</h3>{}</section>",
                    block.title,
                    body,
                )
            )

        if not sections:
            return "Questo template non contiene blocchi compilabili."
        return format_html_join("", "{}", ((section,) for section in sections))
