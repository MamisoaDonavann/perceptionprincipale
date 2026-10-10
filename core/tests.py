"""
Tests du tableau de bord (core).
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class DashboardTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='dash_user',
            password='TestPassword2026!',
        )

    def test_dashboard_requires_login(self):
        """Sans connexion, dashboard inaccessible."""
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)

    def test_dashboard_contains_stats(self):
        """Dashboard affiche les cartes de statistiques."""
        self.client.login(username='dash_user', password='TestPassword2026!')
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        for label in [
            'Agents actifs', 'Missions', 'Gardes validées',
            'Décomptes validés', 'Ordres en cours',
            'Ordres payés', 'Paiements enregistrés',
        ]:
            self.assertContains(response, label)

    def test_dashboard_stats_are_integers(self):
        """Les statistiques retournées sont des entiers."""
        self.client.login(username='dash_user', password='TestPassword2026!')
        response = self.client.get(reverse('dashboard'))
        stats = response.context['stats']
        for key in [
            'agents_actifs', 'missions', 'gardes_validees',
            'decomptes_valides', 'ordres_en_cours',
            'ordres_payes', 'paiements_enregistres',
        ]:
            self.assertIsInstance(stats[key], int)
            self.assertGreaterEqual(stats[key], 0)

    def test_dashboard_contains_username(self):
        """Le nom d'utilisateur apparaît dans le dashboard."""
        self.client.login(username='dash_user', password='TestPassword2026!')
        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, 'dash_user')
