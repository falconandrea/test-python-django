import json

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from .models import Block, BlockResponse, ChecklistItem, Template, Workbook, WorkbookAssignment


class WorkbookFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(username="admin", role="admin")
        cls.moderator = User.objects.create_user(username="moderator", role="moderator")
        cls.other_moderator = User.objects.create_user(username="other-moderator", role="moderator")
        cls.user = User.objects.create_user(username="user", role="user")
        cls.other_user = User.objects.create_user(username="other-user", role="user")
        cls.template = Template.objects.create(name="Struttura", created_by=cls.admin)
        cls.text = Block.objects.create(template=cls.template, title="Domanda", kind="textarea", position=0, content="**Istruzioni**")
        cls.checklist = Block.objects.create(template=cls.template, title="Scelte", kind="checklist", position=1)
        ChecklistItem.objects.create(block=cls.checklist, label="**Opzione**\n\n[Link](https://example.com)", position=0)
        cls.workbook = Workbook.objects.create(name="Copia", source_template=cls.template, moderator=cls.moderator, created_by=cls.admin)
        cls.assignment = WorkbookAssignment.objects.create(workbook=cls.workbook, user=cls.user, created_by=cls.admin)

    def edit_payload(self, workbook, name="Modificato"):
        blocks = list(workbook.blocks.all())
        data = {"name": name, "moderator": self.moderator.pk, "users": [self.user.pk], "action": "save",
                "blocks-TOTAL_FORMS": len(blocks), "blocks-INITIAL_FORMS": len(blocks), "blocks-MIN_NUM_FORMS": 0, "blocks-MAX_NUM_FORMS": 1000}
        for index, block in enumerate(blocks):
            prefix = f"blocks-{index}"
            data.update({f"{prefix}-id": block.pk, f"{prefix}-workbook": workbook.pk, f"{prefix}-title": block.title,
                         f"{prefix}-position": block.position, f"{prefix}-kind": block.kind, f"{prefix}-content": "**Nuove istruzioni**",
                         f"{prefix}-checklist_options": json.dumps([{"id": item.pk, "text": item.label} for item in block.checklist_items.all()])})
        return data

    def test_copy_is_independent_and_future_copies_include_new_fields(self):
        copied = self.workbook.blocks.get(position=1)
        self.assertNotEqual(copied.pk, self.checklist.pk)
        self.assertNotEqual(copied.checklist_items.get().pk, self.checklist.checklist_items.get().pk)
        self.assertEqual(copied.checklist_items.get().label, self.checklist.checklist_items.get().label)
        self.text.content = "Template aggiornato"
        self.text.save()
        Block.objects.create(template=self.template, title="Nuova domanda", kind="textarea", position=2)
        later = Workbook.objects.create(name="Seconda copia", source_template=self.template, moderator=self.moderator, created_by=self.admin)
        self.assertEqual(self.workbook.blocks.count(), 2)
        self.assertEqual(self.workbook.blocks.get(position=0).content, "**Istruzioni**")
        self.assertEqual(later.blocks.count(), 3)
        self.assertEqual(later.blocks.get(position=0).content, "Template aggiornato")
        later.name = "Rinominato"
        later.save()
        self.assertEqual(later.blocks.count(), 3)

    def test_users_cannot_see_or_submit_drafts(self):
        self.client.force_login(self.user)
        url = reverse("workbook-fill", args=[self.workbook.pk])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url, {}).status_code, 404)
        self.assertNotContains(self.client.get(reverse("dashboard")), self.workbook.name)
        self.assertFalse(BlockResponse.objects.exists())

    def test_confirmed_workbook_only_accepts_assigned_user(self):
        self.workbook.confirm(self.moderator)
        self.client.force_login(self.user)
        url = reverse("workbook-fill", args=[self.workbook.pk])
        page = self.client.get(url)
        self.assertContains(page, "<strong>Istruzioni</strong>", html=True)
        copied_text = self.workbook.blocks.get(position=0)
        copied_checklist = self.workbook.blocks.get(position=1)
        item = copied_checklist.checklist_items.get()
        payload = {f"text_{copied_text.pk}": "Risposta", f"checklist_{copied_checklist.pk}": [item.pk]}
        self.assertEqual(self.client.post(url, payload).status_code, 302)
        response = self.assignment.responses.get(block=copied_checklist)
        self.assertEqual(list(response.checked_items.values_list("pk", flat=True)), [item.pk])
        self.client.force_login(self.other_user)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url, payload).status_code, 404)
        self.client.force_login(self.user)
        self.assignment.is_active = False
        self.assignment.save()
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_moderator_can_edit_draft_and_confirm_but_cannot_edit_confirmed(self):
        self.client.force_login(self.moderator)
        url = reverse("workbook-edit", args=[self.workbook.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        payload = self.edit_payload(self.workbook)
        payload["action"] = "confirm"
        self.assertEqual(self.client.post(url, payload).status_code, 302)
        self.workbook.refresh_from_db()
        self.assertTrue(self.workbook.is_confirmed)
        self.assertEqual(self.workbook.blocks.get(position=0).content, "**Nuove istruzioni**")
        self.assertEqual(self.client.post(url, self.edit_payload(self.workbook, "Non consentito")).status_code, 404)
        self.workbook.refresh_from_db()
        self.assertEqual(self.workbook.name, "Modificato")
        self.assertEqual(self.client.get(reverse("workbook-responses", args=[self.workbook.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("template-edit", args=[self.template.pk])).status_code, 404)
        self.client.force_login(self.other_moderator)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.get(reverse("workbook-responses", args=[self.workbook.pk])).status_code, 404)

    def test_admin_can_edit_confirmed_workbook_frontend_and_backoffice(self):
        self.workbook.confirm(self.admin)
        self.client.force_login(self.admin)
        original_option = self.workbook.blocks.get(position=1).checklist_items.get().pk
        payload = self.edit_payload(self.workbook)
        self.assertEqual(self.client.post(reverse("workbook-edit", args=[self.workbook.pk]), payload).status_code, 302)
        payload = self.edit_payload(self.workbook, "Modificato nel backoffice")
        self.assertEqual(self.client.post(reverse("admin:workflows_workbook_change", args=[self.workbook.pk]), payload).status_code, 302)
        self.workbook.refresh_from_db()
        self.assertEqual(self.workbook.name, "Modificato nel backoffice")
        self.assertTrue(self.workbook.is_confirmed)
        self.assertEqual(self.workbook.blocks.get(position=0).content, "**Nuove istruzioni**")
        self.assertEqual(self.workbook.blocks.get(position=1).checklist_items.get().pk, original_option)
        self.assertEqual(self.text.content, "**Istruzioni**")

    def test_workbook_creation_in_frontend_and_backoffice_copies_once(self):
        self.client.force_login(self.admin)
        payload = {"name": "Creato nel frontend", "source_template": self.template.pk, "moderator": self.moderator.pk, "users": [self.user.pk]}
        self.assertEqual(self.client.post(reverse("workbook-create"), payload).status_code, 302)
        created = Workbook.objects.get(name=payload["name"])
        self.assertEqual(created.blocks.count(), 2)
        self.assertTrue(created.assignments.filter(user=self.user, is_active=True).exists())
        payload["name"] = "Creato nel backoffice"
        self.assertEqual(self.client.post(reverse("admin:workflows_workbook_add"), payload).status_code, 302)
        created = Workbook.objects.get(name=payload["name"])
        self.assertEqual(created.blocks.count(), 2)
        self.assertTrue(created.assignments.filter(user=self.user, is_active=True).exists())

    def test_confirmed_workbook_users_can_be_changed_by_moderator(self):
        self.workbook.confirm(self.moderator)
        self.client.force_login(self.moderator)
        url = reverse("workbook-responses", args=[self.workbook.pk])
        self.assertEqual(self.client.post(url, {"users": [self.other_user.pk]}).status_code, 302)
        self.assignment.refresh_from_db()
        self.assertFalse(self.assignment.is_active)
        self.assertTrue(self.workbook.assignments.filter(user=self.other_user, is_active=True).exists())
        self.assertEqual(self.workbook.status, Workbook.Status.CONFIRMED)

    def test_user_does_not_have_management_access(self):
        self.client.force_login(self.user)
        self.assertFalse(self.user.is_staff)
        for url in (reverse("workbook-edit", args=[self.workbook.pk]), reverse("workbook-responses", args=[self.workbook.pk]), reverse("template-edit", args=[self.template.pk]), reverse("workbook-create")):
            self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.get(reverse("admin:index")).status_code, 302)

    def test_moderator_admin_inline_shows_all_workbook_blocks_in_draft_and_confirmed(self):
        self.client.force_login(self.moderator)
        url = reverse("admin:workflows_workbook_change", args=[self.workbook.pk])
        page = self.client.get(url)
        self.assertEqual(page.status_code, 200)
        inline = page.context["inline_admin_formsets"][0]
        expected = list(self.workbook.blocks.values_list("pk", flat=True))
        self.assertEqual([form.instance.pk for form in inline.formset.initial_forms], expected)
        self.assertTrue(inline.has_change_permission)
        self.workbook.confirm(self.moderator)
        page = self.client.get(url)
        inline = page.context["inline_admin_formsets"][0]
        self.assertEqual([form.instance.pk for form in inline.formset.initial_forms], expected)
        self.assertFalse(inline.has_change_permission)
        self.assertFalse(inline.has_add_permission)
        self.assertFalse(inline.has_delete_permission)
        self.client.force_login(self.other_moderator)
        self.assertRedirects(self.client.get(url), reverse("admin:index"))
