from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from .models import JournalAudit
from .services import journaliser

User = get_user_model()


class JournalAuditModelTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='audit_user',
            password='test_password_2026'
        )

    def test_creation_entree_audit(self):
        entry = JournalAudit.objects.create(
            id_utilisateur=self.user,
            action=JournalAudit.ACTION_CREATION,
            entite_concernee='gardes.Garde',
            id_entite_concernee=1,
            commentaire='Test',
        )
        self.assertIsNotNone(entry.pk)
        self.assertEqual(JournalAudit.objects.count(), 1)

    def test_modification_refusee(self):
        entry = JournalAudit.objects.create(
            id_utilisateur=self.user,
            action=JournalAudit.ACTION_CREATION,
            entite_concernee='gardes.Garde',
            id_entite_concernee=1,
        )
        entry.commentaire = "tentative de modification"
        with self.assertRaises(ValidationError):
            entry.save()

    def test_suppression_refusee(self):
        entry = JournalAudit.objects.create(
            id_utilisateur=self.user,
            action=JournalAudit.ACTION_CREATION,
            entite_concernee='gardes.Garde',
            id_entite_concernee=1,
        )
        with self.assertRaises(ValidationError):
            entry.delete()


class JournaliserServiceTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='audit_user',
            password='test_password_2026'
        )

    def test_journaliser_cree_entree(self):
        entry = journaliser(
            user=self.user,
            action=JournalAudit.ACTION_CREATION,
            entite='gardes.Garde',
            id_entite=42,
            commentaire='Création de test',
        )
        self.assertEqual(entry.action, JournalAudit.ACTION_CREATION)
        self.assertEqual(entry.entite_concernee, 'gardes.Garde')
        self.assertEqual(entry.id_entite_concernee, 42)

    def test_journaliser_refuse_action_inconnue(self):
        with self.assertRaises(ValidationError):
            journaliser(
                user=self.user,
                action='ACTION_INVENTEE',
                entite='gardes.Garde',
                id_entite=1,
            )

    def test_journaliser_avec_valeurs_avant_apres(self):
        entry = journaliser(
            user=self.user,
            action=JournalAudit.ACTION_MODIFICATION,
            entite='gardes.Garde',
            id_entite=42,
            avant={'statut': 'VALIDEE'},
            apres={'statut': 'ANNULEE'},
        )
        self.assertEqual(entry.valeurs_avant, {'statut': 'VALIDEE'})
        self.assertEqual(entry.valeurs_apres, {'statut': 'ANNULEE'})


class JournalAuditAdminTests(TestCase):

    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            username='admin_test',
            password='test_password_2026',
            email='admin@test.local',
        )
        self.client.force_login(self.admin_user)

    def test_admin_lecture_seule(self):
        from django.urls import reverse
        url_add = reverse('admin:audit_journalaudit_add')
        response = self.client.get(url_add)
        # L'admin refuse l'accès : redirection (302) ou 403
        self.assertIn(response.status_code, (302, 403))
