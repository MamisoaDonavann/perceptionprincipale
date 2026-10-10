"""
Tests de l'application rapports.
"""

from datetime import date, datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from agents.models import Agent
from gardes.models import Garde
from paiements.models import OrdrePaiement
from tarifs.models import Tarif

from .services import (
    generer_etat_decompte_pdf,
    generer_historique_agent_excel,
    generer_historique_agent_pdf,
    generer_liste_paiement_pdf,
)

User = get_user_model()


def _dt(y, m, d, h=0):
    return timezone.make_aware(datetime(y, m, d, h, 0, 0))


class BaseRapportTest(TestCase):

    def setUp(self):
        call_command('setup_groups', verbosity=0)
        # Superuser pour tout tester
        self.user = User.objects.create_superuser(
            username='admin_test',
            password='TestPassword2026!',
            email='admin@test.local',
        )
        self.agent = Agent.objects.create(
            matricule='AG-R-001', nom='Rakoto', prenoms='Jean'
        )
        self.tarif = Tarif.objects.create(
            montant_partiel=Decimal('15000.00'),
            date_debut_validite=date(2025, 1, 1),
            id_utilisateur_createur=self.user,
        )

    def _garde(self, mois):
        g = Garde(
            agent=self.agent, tarif=self.tarif,
            date_heure_debut=_dt(2026, mois, 1, 6),
            date_heure_fin=_dt(2026, mois, 1, 18),
            id_utilisateur_saisie=self.user,
        )
        g._recalculer()
        g.full_clean(exclude=None, validate_unique=False)
        g.save()
        return g

    def _decompte_valide(self):
        from decomptes.services import creer_decompte, valider_decompte
        self._garde(6)
        d, _ = creer_decompte(self.agent, 2026, 6, self.user)
        valider_decompte(d, self.user)
        d.refresh_from_db()
        return d


class IndexRapportsViewTests(BaseRapportTest):

    def test_requires_login(self):
        r = self.client.get(reverse('rapports:index'))
        self.assertEqual(r.status_code, 302)

    def test_accessible_when_logged(self):
        self.client.login(username='admin_test', password='TestPassword2026!')
        r = self.client.get(reverse('rapports:index'))
        self.assertEqual(r.status_code, 200)


class EtatDecomptePdfViewTests(BaseRapportTest):

    def test_requires_permission(self):
        u = User.objects.create_user(username='no_perm_r', password='x')
        self.client.login(username='no_perm_r', password='x')
        d = self._decompte_valide()
        r = self.client.get(reverse('rapports:etat_decompte_pdf', args=[d.pk]))
        self.assertEqual(r.status_code, 403)

    def test_pdf_generated(self):
        d = self._decompte_valide()
        self.client.login(username='admin_test', password='TestPassword2026!')
        r = self.client.get(reverse('rapports:etat_decompte_pdf', args=[d.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/pdf')
        self.assertTrue(r.content.startswith(b'%PDF'))
        self.assertGreater(len(r.content), 1000)

    def test_brouillon_refused(self):
        from decomptes.services import creer_decompte
        self._garde(6)
        d, _ = creer_decompte(self.agent, 2026, 6, self.user)
        self.client.login(username='admin_test', password='TestPassword2026!')
        r = self.client.get(
            reverse('rapports:etat_decompte_pdf', args=[d.pk])
        )
        self.assertEqual(r.status_code, 302)  # redirigé


class ListePaiementPdfViewTests(BaseRapportTest):

    def _op_valide(self):
        from paiements.services import creer_ordre_paiement, valider_ordre_paiement
        d = self._decompte_valide()
        op, _ = creer_ordre_paiement(self.agent, 2026, [d], self.user)
        return valider_ordre_paiement(op, self.user)

    def test_pdf_generated(self):
        op = self._op_valide()
        self.client.login(username='admin_test', password='TestPassword2026!')
        r = self.client.get(
            reverse('rapports:liste_paiement_pdf', args=[op.pk])
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/pdf')
        self.assertTrue(r.content.startswith(b'%PDF'))


class HistoriqueAgentViewTests(BaseRapportTest):

    def test_pdf_generated(self):
        self.client.login(username='admin_test', password='TestPassword2026!')
        r = self.client.get(
            reverse('rapports:historique_agent_pdf', args=[self.agent.pk])
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/pdf')
        self.assertTrue(r.content.startswith(b'%PDF'))

    def test_excel_generated(self):
        self.client.login(username='admin_test', password='TestPassword2026!')
        r = self.client.get(
            reverse('rapports:historique_agent_excel', args=[self.agent.pk])
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn('spreadsheetml', r['Content-Type'])
        # Signature ZIP de xlsx
        self.assertTrue(r.content.startswith(b'PK'))

    def test_date_invalide_redirige(self):
        self.client.login(username='admin_test', password='TestPassword2026!')
        r = self.client.get(
            reverse('rapports:historique_agent_pdf', args=[self.agent.pk]),
            {'date_debut': 'not-a-date'},
        )
        self.assertEqual(r.status_code, 302)  # redirigé avec message d'erreur


class AuditExportTests(BaseRapportTest):

    def test_export_journalise(self):
        from audit.models import JournalAudit
        self.client.login(username='admin_test', password='TestPassword2026!')
        self.client.get(
            reverse('rapports:historique_agent_pdf', args=[self.agent.pk])
        )
        self.assertTrue(
            JournalAudit.objects.filter(
                action=JournalAudit.ACTION_EXPORT,
                entite_concernee='agents.Agent',
            ).exists()
        )


class ServicesGenerateursTests(BaseRapportTest):

    def test_pdf_etat_decompte_bytes(self):
        d = self._decompte_valide()
        buf = generer_etat_decompte_pdf(d)
        content = buf.getvalue()
        self.assertTrue(content.startswith(b'%PDF'))
        self.assertGreater(len(content), 1000)

    def test_pdf_historique_bytes(self):
        buf = generer_historique_agent_pdf(self.agent)
        self.assertTrue(buf.getvalue().startswith(b'%PDF'))

    def test_excel_historique_bytes(self):
        buf = generer_historique_agent_excel(self.agent)
        self.assertTrue(buf.getvalue().startswith(b'PK'))
