"""
Tests d'authentification et de configuration des groupes/permissions.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class AuthenticationTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', password='TestPassword2026!',
        )

    def test_dashboard_requires_login(self):
        r = self.client.get(reverse('core:dashboard'))
        self.assertEqual(r.status_code, 302)
        self.assertIn(reverse('login'), r.url)

    def test_login_valid_credentials(self):
        r = self.client.post(reverse('login'), {
            'username': 'testuser',
            'password': 'TestPassword2026!',
        })
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, reverse('core:dashboard'))

    def test_login_invalid_credentials(self):
        r = self.client.post(reverse('login'), {
            'username': 'testuser',
            'password': 'WrongPassword',
        })
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'incorrect')

    def test_logout_by_post(self):
        self.client.login(username='testuser', password='TestPassword2026!')
        r = self.client.post(reverse('logout'))
        self.assertEqual(r.status_code, 302)

    def test_logout_by_get_refused(self):
        self.client.login(username='testuser', password='TestPassword2026!')
        r = self.client.get(reverse('logout'))
        self.assertEqual(r.status_code, 405)


class SetupGroupsCommandTests(TestCase):
    """Tests de la commande setup_groups."""

    def test_commande_cree_les_3_groupes(self):
        call_command('setup_groups', verbosity=0)
        for nom in ['Administrateur', 'Percepteur', 'Operateur']:
            self.assertTrue(Group.objects.filter(name=nom).exists())

    def test_permission_custom_annuler_garde(self):
        call_command('setup_groups', verbosity=0)
        self.assertTrue(
            Permission.objects.filter(
                content_type__app_label='gardes',
                codename='annuler_garde',
            ).exists()
        )

    def test_administrateur_lecture_seule_metier(self):
        call_command('setup_groups', verbosity=0)
        g = Group.objects.get(name='Administrateur')
        codes = set(
            g.permissions.values_list(
                'content_type__app_label', 'codename'
            )
        )
        # Lecture seule
        self.assertIn(('agents', 'view_agent'), codes)
        self.assertIn(('gardes', 'view_garde'), codes)
        self.assertIn(('paiements', 'view_ordrepaiement'), codes)
        # Aucune écriture métier
        self.assertNotIn(('agents', 'add_agent'), codes)
        self.assertNotIn(('gardes', 'add_garde'), codes)
        self.assertNotIn(('paiements', 'enregistrer_paiement'), codes)

    def test_percepteur_a_les_9_permissions_paiements(self):
        call_command('setup_groups', verbosity=0)
        g = Group.objects.get(name='Percepteur')
        codes = set(
            g.permissions.filter(content_type__app_label='paiements')
            .values_list('codename', flat=True)
        )
        for code in [
            'creer_ordre_paiement', 'valider_ordre_paiement',
            'annuler_ordre_paiement', 'enregistrer_paiement',
            'annuler_paiement', 'confirmer_reception',
            'annuler_confirmation', 'consulter_ordre_paiement',
            'cloturer_ordre_paiement',
        ]:
            self.assertIn(code, codes, msg=f"Permission {code} absente")

    def test_operateur_pas_change_garde(self):
        call_command('setup_groups', verbosity=0)
        g = Group.objects.get(name='Operateur')
        codes = set(
            g.permissions.filter(content_type__app_label='gardes')
            .values_list('codename', flat=True)
        )
        self.assertIn('add_garde', codes)
        self.assertIn('view_garde', codes)
        self.assertNotIn('change_garde', codes)
        self.assertNotIn('annuler_garde', codes)

    def test_operateur_pas_validation_decompte(self):
        call_command('setup_groups', verbosity=0)
        g = Group.objects.get(name='Operateur')
        codes = set(
            g.permissions.filter(content_type__app_label='decomptes')
            .values_list('codename', flat=True)
        )
        self.assertIn('add_decompte', codes)
        self.assertNotIn('change_decompte', codes)

    def test_operateur_pas_audit(self):
        call_command('setup_groups', verbosity=0)
        g = Group.objects.get(name='Operateur')
        self.assertEqual(
            g.permissions.filter(content_type__app_label='audit').count(),
            0,
        )

    def test_commande_idempotente(self):
        call_command('setup_groups', verbosity=0)
        count_1 = {g.name: g.permissions.count() for g in Group.objects.all()}
        call_command('setup_groups', verbosity=0)
        count_2 = {g.name: g.permissions.count() for g in Group.objects.all()}
        self.assertEqual(count_1, count_2)

    def test_reset_reassigne(self):
        call_command('setup_groups', verbosity=0)
        g = Group.objects.get(name='Operateur')
        # Ajouter une permission parasite
        extra = Permission.objects.get(
            content_type__app_label='audit',
            codename='view_journalaudit',
        )
        g.permissions.add(extra)
        self.assertEqual(
            g.permissions.filter(content_type__app_label='audit').count(), 1
        )
        # Reset
        call_command('setup_groups', '--reset', verbosity=0)
        g.refresh_from_db()
        self.assertEqual(
            g.permissions.filter(content_type__app_label='audit').count(), 0
        )

    def test_percepteur_change_garde_mais_pas_admin(self):
        """change_garde autorise la modification, mais la vue annuler exige annuler_garde."""
        call_command('setup_groups', verbosity=0)
        g_perm = Group.objects.get(name='Percepteur')
        self.assertTrue(
            g_perm.permissions.filter(
                content_type__app_label='gardes',
                codename='change_garde',
            ).exists()
        )
        self.assertTrue(
            g_perm.permissions.filter(
                content_type__app_label='gardes',
                codename='annuler_garde',
            ).exists()
        )
