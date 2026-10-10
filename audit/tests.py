"""
Tests UI journal d'audit.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from .models import JournalAudit

User = get_user_model()


class BaseAuditViewTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='audit_user', password='TestPassword2026!'
        )
        self.user.user_permissions.add(
            Permission.objects.get(
                codename='view_journalaudit',
                content_type__app_label='audit',
            )
        )
        self.entry = JournalAudit.objects.create(
            id_utilisateur=self.user,
            action=JournalAudit.ACTION_CREATION,
            entite_concernee='test.Model',
            id_entite_concernee=42,
            commentaire='Test',
        )


class AuditListViewTests(BaseAuditViewTest):

    def test_requires_login(self):
        r = self.client.get(reverse('audit:list'))
        self.assertEqual(r.status_code, 302)

    def test_requires_permission(self):
        u = User.objects.create_user(username='noperm_a', password='x')
        self.client.login(username='noperm_a', password='x')
        r = self.client.get(reverse('audit:list'))
        self.assertEqual(r.status_code, 403)

    def test_accessible(self):
        self.client.login(username='audit_user', password='TestPassword2026!')
        r = self.client.get(reverse('audit:list'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'test.Model')

    def test_filter_action(self):
        self.client.login(username='audit_user', password='TestPassword2026!')
        r = self.client.get(reverse('audit:list'), {'action': 'CREATION'})
        self.assertEqual(len(r.context['page'].object_list), 1)

        r = self.client.get(reverse('audit:list'), {'action': 'ANNULATION'})
        self.assertEqual(len(r.context['page'].object_list), 0)


class AuditDetailViewTests(BaseAuditViewTest):

    def test_detail_accessible(self):
        self.client.login(username='audit_user', password='TestPassword2026!')
        r = self.client.get(reverse('audit:detail', args=[self.entry.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'test.Model')

    def test_404_unknown(self):
        self.client.login(username='audit_user', password='TestPassword2026!')
        r = self.client.get(reverse('audit:detail', args=[99999]))
        self.assertEqual(r.status_code, 404)
