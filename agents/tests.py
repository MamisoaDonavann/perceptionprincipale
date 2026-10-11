"""
Tests CRUD agents.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from .models import Agent

User = get_user_model()


class BaseAgentTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='agent_user',
            password='TestPassword2026!',
        )
        # Accorder toutes les permissions agents
        for codename in ['add_agent', 'change_agent', 'view_agent']:
            self.user.user_permissions.add(
                Permission.objects.get(
                    codename=codename,
                    content_type__app_label='agents',
                )
            )
        self.agent = Agent.objects.create(
            matricule='AG-TEST-001',
            nom='Rakoto',
            prenoms='Jean',
        )


class AgentListViewTests(BaseAgentTest):

    def test_requires_login(self):
        response = self.client.get(reverse('agents:list'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_requires_view_permission(self):
        u = User.objects.create_user(username='noperm', password='x')
        self.client.login(username='noperm', password='x')
        response = self.client.get(reverse('agents:list'))
        self.assertEqual(response.status_code, 403)

    def test_accessible_with_permission(self):
        self.client.login(username='agent_user', password='TestPassword2026!')
        response = self.client.get(reverse('agents:list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'AG-TEST-001')

    def test_search_filters(self):
        self.client.login(username='agent_user', password='TestPassword2026!')
        response = self.client.get(reverse('agents:list'), {'q': 'Rakoto'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'AG-TEST-001')

        response = self.client.get(reverse('agents:list'), {'q': 'XYZ'})
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'AG-TEST-001')

    def test_filter_statut(self):
        self.client.login(username='agent_user', password='TestPassword2026!')
        response = self.client.get(reverse('agents:list'), {'statut': 'ACTIF'})
        self.assertContains(response, 'AG-TEST-001')

        response = self.client.get(reverse('agents:list'), {'statut': 'RADIE'})
        self.assertNotContains(response, 'AG-TEST-001')


class AgentDetailViewTests(BaseAgentTest):

    def test_accessible_with_permission(self):
        self.client.login(username='agent_user', password='TestPassword2026!')
        response = self.client.get(reverse('agents:detail', args=[self.agent.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Rakoto')

    def test_404_on_unknown(self):
        self.client.login(username='agent_user', password='TestPassword2026!')
        response = self.client.get(reverse('agents:detail', args=[99999]))
        self.assertEqual(response.status_code, 404)


class AgentCreateViewTests(BaseAgentTest):

    def test_create_requires_add_permission(self):
        u = User.objects.create_user(username='viewer', password='x')
        u.user_permissions.add(Permission.objects.get(
            codename='view_agent', content_type__app_label='agents'
        ))
        self.client.login(username='viewer', password='x')
        response = self.client.get(reverse('agents:create'))
        self.assertEqual(response.status_code, 403)

    def test_create_agent_success(self):
        self.client.login(username='agent_user', password='TestPassword2026!')
        response = self.client.post(reverse('agents:create'), {
            'matricule': 'AG-TEST-002',
            'nom': 'Rabe',
            'prenoms': 'Marie',
            'statut_agent': 'ACTIF',
            'actif': 'on',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Agent.objects.filter(matricule='AG-TEST-002').exists())

    def test_create_duplicate_matricule_refused(self):
        self.client.login(username='agent_user', password='TestPassword2026!')
        response = self.client.post(reverse('agents:create'), {
            'matricule': 'AG-TEST-001',
            'nom': 'Dup',
            'prenoms': 'Duplicata',
            'statut_agent': 'ACTIF',
            'actif': 'on',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'existe déjà')


class AgentUpdateViewTests(BaseAgentTest):

    def test_update_agent_success(self):
        self.client.login(username='agent_user', password='TestPassword2026!')
        response = self.client.post(
            reverse('agents:update', args=[self.agent.pk]),
            {
                'matricule': 'AG-TEST-001',
                'nom': 'Rakoto',
                'prenoms': 'Jean',
                'statut_agent': 'SUSPENDU',
                'actif': 'on',
            }
        )
        self.assertEqual(response.status_code, 302)
        self.agent.refresh_from_db()
        self.assertEqual(self.agent.statut_agent, 'SUSPENDU')


class AgentToggleActifTests(BaseAgentTest):

    def test_desactivation_reussie(self):
        self.client.login(username='agent_user', password='TestPassword2026!')
        r = self.client.post(
            reverse('agents:toggle_actif', args=[self.agent.pk])
        )
        self.assertEqual(r.status_code, 302)
        self.agent.refresh_from_db()
        self.assertFalse(self.agent.actif)

    def test_reactivation_reussie_si_non_radie(self):
        self.agent.actif = False
        self.agent.save()
        self.client.login(username='agent_user', password='TestPassword2026!')
        r = self.client.post(
            reverse('agents:toggle_actif', args=[self.agent.pk])
        )
        self.assertEqual(r.status_code, 302)
        self.agent.refresh_from_db()
        self.assertTrue(self.agent.actif)

    def test_reactivation_refusee_si_radie(self):
        self.agent.actif = False
        self.agent.statut_agent = 'RADIE'
        self.agent.save()
        self.client.login(username='agent_user', password='TestPassword2026!')
        r = self.client.post(
            reverse('agents:toggle_actif', args=[self.agent.pk])
        )
        self.assertEqual(r.status_code, 302)
        self.agent.refresh_from_db()
        self.assertFalse(self.agent.actif)

    def test_toggle_requires_post(self):
        self.client.login(username='agent_user', password='TestPassword2026!')
        r = self.client.get(
            reverse('agents:toggle_actif', args=[self.agent.pk])
        )
        self.assertEqual(r.status_code, 405)

    def test_toggle_requires_permission(self):
        u = User.objects.create_user(username='no_perm_toggle', password='x')
        self.client.login(username='no_perm_toggle', password='x')
        r = self.client.post(
            reverse('agents:toggle_actif', args=[self.agent.pk])
        )
        self.assertEqual(r.status_code, 403)

    def test_toggle_journalise(self):
        from audit.models import JournalAudit
        self.client.login(username='agent_user', password='TestPassword2026!')
        self.client.post(
            reverse('agents:toggle_actif', args=[self.agent.pk])
        )
        self.assertTrue(
            JournalAudit.objects.filter(
                entite_concernee='agents.Agent',
                id_entite_concernee=self.agent.pk,
                action=JournalAudit.ACTION_MODIFICATION,
            ).exists()
        )
