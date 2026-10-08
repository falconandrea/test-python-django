from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models import Count, Max
from django.urls import reverse
from django.utils.html import format_html, format_html_join

from .forms import BlockInlineForm, BlockInlineFormSet
from .models import Block, ShareLink, Template
from .utils import render_markdown

User = get_user_model()


def is_admin_user(user):
    return user.is_authenticated and (user.is_superuser or user.is_admin)


def can_access_template(user, template):
    return is_admin_user(user) or template.moderators.filter(pk=user.pk).exists()


class BlockInline(admin.TabularInline):
    model = Block
    form = BlockInlineForm
    formset = BlockInlineFormSet
    fields = ("position", "title", "kind", "content", "checklist_options", "required")
    ordering = ("position", "pk")
    extra = 1
    show_change_link = False

    def checklist_options(self, obj):
        return format_html_join("", "<div>{}</div>", ((render_markdown(item.label),) for item in obj.checklist_items.all()))

    def has_view_permission(self, request, obj=None):
        return bool(
            request.user.is_authenticated
            and request.user.is_staff
            and (obj is None or can_access_template(request.user, obj))
        )

    def has_add_permission(self, request, obj=None):
        if not self.has_view_permission(request, obj):
            return False
        return obj is None or not obj.is_confirmed

    def has_change_permission(self, request, obj=None):
        if not self.has_view_permission(request, obj):
            return False
        return obj is None or not obj.is_confirmed

    def has_delete_permission(self, request, obj=None):
        return self.has_change_permission(request, obj)

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.is_confirmed:
            return self.fields
        return ()


@admin.register(Template)
class TemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "status", "block_count", "moderator_names", "created_by")
    list_filter = ("status",)
    search_fields = ("name", "moderators__username", "created_by__username")
    list_select_related = ("created_by", "confirmed_by")
    filter_horizontal = ("moderators",)
    inlines = (BlockInline,)
    fieldsets = (
        (None, {"fields": ("name", "moderators")}),
        (
            "Stato e cronologia",
            {"fields": ("status", "created_by", "created_at", "updated_at", "confirmed_by", "confirmed_at", "duplicated_from")},
        ),
    )
    readonly_fields = (
        "status",
        "created_by",
        "created_at",
        "updated_at",
        "confirmed_by",
        "confirmed_at",
        "duplicated_from",
    )
    actions = ("confirm_selected", "duplicate_selected")

    def get_queryset(self, request):
        queryset = super().get_queryset(request).annotate(_block_count=Count("blocks", distinct=True))
        if is_admin_user(request.user):
            return queryset
        return queryset.filter(moderators=request.user).distinct()

    def has_module_permission(self, request):
        return bool(
            request.user.is_authenticated
            and request.user.is_staff
            and (is_admin_user(request.user) or request.user.role == "moderator")
        )

    def has_view_permission(self, request, obj=None):
        if not self.has_module_permission(request):
            return False
        return obj is None or can_access_template(request.user, obj)

    def has_add_permission(self, request):
        return is_admin_user(request.user)

    def has_change_permission(self, request, obj=None):
        if not self.has_module_permission(request):
            return False
        if obj is None:
            return True
        return can_access_template(request.user, obj) and not obj.is_confirmed

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        if not is_admin_user(request.user):
            readonly.append("moderators")
        if obj and obj.is_confirmed:
            readonly.extend(("name", "moderators"))
        return tuple(dict.fromkeys(readonly))

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        field = super().formfield_for_manytomany(db_field, request, **kwargs)
        if db_field.name == "moderators":
            field.queryset = field.queryset.filter(is_active=True, is_superuser=False)
        return field

    @admin.display(description="Blocchi", ordering="_block_count")
    def block_count(self, obj):
        return obj._block_count

    @admin.display(description="Moderatori")
    def moderator_names(self, obj):
        return ", ".join(obj.moderators.values_list("username", flat=True)) or "—"

    @admin.action(description="Conferma e blocca i template selezionati", permissions=("change",))
    def confirm_selected(self, request, queryset):
        confirmed = 0
        for template in queryset.filter(status=Template.Status.DRAFT):
            try:
                template.confirm(request.user)
            except ValidationError as error:
                self.message_user(
                    request,
                    f'"{template.name}": {" ".join(error.messages)}',
                    level=messages.ERROR,
                )
            else:
                confirmed += 1
        if confirmed:
            self.message_user(request, f"Confermati {confirmed} template.", level=messages.SUCCESS)

    @admin.action(description="Duplica i template selezionati", permissions=("change",))
    def duplicate_selected(self, request, queryset):
        if not is_admin_user(request.user):
            self.message_user(request, "Solo un admin può duplicare i template.", level=messages.ERROR)
            return
        copies = [template.duplicate(request.user) for template in queryset]
        self.message_user(request, f"Create {len(copies)} copie in bozza.", level=messages.SUCCESS)

    def get_actions(self, request):
        actions = super().get_actions(request)
        if not is_admin_user(request.user):
            actions.pop("duplicate_selected", None)
        return actions


@admin.register(ShareLink)
class ShareLinkAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "template",
        "is_active",
        "last_response_update",
        "created_by",
        "created_at",
        "public_link",
    )
    list_filter = ("is_active", "template")
    search_fields = ("name", "template__name")
    list_editable = ("is_active",)
    readonly_fields = ("token", "created_by", "created_at", "public_url", "answers_summary")
    fields = (
        "template",
        "name",
        "is_active",
        "answers_summary",
        "token",
        "public_url",
        "created_by",
        "created_at",
    )
    change_form_template = "admin/workflows/sharelink/change_form.html"

    def get_queryset(self, request):
        queryset = (
            super()
            .get_queryset(request)
            .select_related("template", "created_by")
            .annotate(_last_response_update=Max("responses__updated_at"))
            .prefetch_related("template__blocks__checklist_items", "responses__checked_items")
        )
        if is_admin_user(request.user):
            return queryset
        return queryset.filter(template__moderators=request.user).distinct()

    def get_fields(self, request, obj=None):
        fields = list(super().get_fields(request, obj))
        if obj is None:
            fields.remove("answers_summary")
        return fields

    def has_module_permission(self, request):
        return bool(
            request.user.is_authenticated
            and request.user.is_staff
            and (is_admin_user(request.user) or request.user.role == "moderator")
        )

    def has_view_permission(self, request, obj=None):
        if not self.has_module_permission(request):
            return False
        return obj is None or can_access_template(request.user, obj.template)

    def has_add_permission(self, request):
        return self.has_module_permission(request)

    def has_change_permission(self, request, obj=None):
        return self.has_view_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return False

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "template":
            templates = Template.objects.filter(status=Template.Status.CONFIRMED)
            if not is_admin_user(request.user):
                templates = templates.filter(moderators=request.user)
            kwargs["queryset"] = templates.order_by("name").distinct()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        if not can_access_template(request.user, obj.template):
            raise ValidationError("Puoi creare link solo per i template assegnati a te.")
        if not change:
            obj.created_by = request.user
        obj.full_clean()
        super().save_model(request, obj, form, change)

    @admin.display(description="Link pubblico")
    def public_url(self, obj):
        if not obj.pk:
            return "Il link sarà disponibile dopo il salvataggio."
        path = reverse("public-form", args=(obj.token,))
        return format_html('<a href="{}" target="_blank" rel="noopener">{}</a>', path, path)

    @admin.display(description="Apri link")
    def public_link(self, obj):
        path = reverse("public-form", args=(obj.token,))
        return format_html('<a href="{}" target="_blank" rel="noopener">Apri compilazione</a>', path)

    @admin.display(description="Ultima risposta", ordering="_last_response_update", empty_value="—")
    def last_response_update(self, obj):
        return obj._last_response_update

    @admin.display(description="Risposte della persona")
    def answers_summary(self, obj):
        responses = {response.block_id: response for response in obj.responses.all()}
        sections = []

        for block in obj.template.blocks.all():
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

    def render_change_form(self, request, context, add=False, change=False, form_url="", obj=None):
        if obj and obj.pk:
            context["full_public_url"] = request.build_absolute_uri(
                reverse("public-form", args=(obj.token,))
            )
        return super().render_change_form(request, context, add, change, form_url, obj)
