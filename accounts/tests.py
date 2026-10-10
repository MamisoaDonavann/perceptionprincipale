"""
Tests d'authentification et de protection du dashboard.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class AuthenticationTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='TestPassword2026!',
        )

    def test_dashboard_requires_login(self):
        """Sans connexion, / redirige vers la page de login."""
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)

    def test_login_page_accessible(self):
        """La page de login est accessible sans connexion."""
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'PERCEPTION MAROVOAY')

    def test_login_valid_credentials(self):
        """Login avec identifiants corrects → redirection vers dashboard."""
        response = self.client.post(reverse('login'), {
            'username': 'testuser',
            'password': 'TestPassword2026!',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('dashboard'))

    def test_login_invalid_credentials(self):
        """Login avec identifiants incorrects → reste sur login."""
        response = self.client.post(reverse('login'), {
            'username': 'testuser',
            'password': 'WrongPassword',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'incorrect')

    def test_dashboard_accessible_after_login(self):
        """Après connexion, / est accessible."""
        self.client.login(username='testuser', password='TestPassword2026!')
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Tableau de bord')

    def test_logout_by_post(self):
        """Logout par POST → 302 vers logged_out."""
        self.client.login(username='testuser', password='TestPassword2026!')
        response = self.client.post(reverse('logout'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('logged_out'), response.url)

    def test_logout_by_get_refused(self):
        """Logout par GET → 405 Method Not Allowed."""
        self.client.login(username='testuser', password='TestPassword2026!')
        response = self.client.get(reverse('logout'))
        self.assertEqual(response.status_code, 405)

    def test_logged_out_page_accessible(self):
        """La page logged_out est accessible."""
        response = self.client.get(reverse('logged_out'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Déconnexion réussie')
