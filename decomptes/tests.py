"""
Tests UI décomptes.
"""

from datetime import date, datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from agents.models import Agent
from gardes.models import Garde
from tarifs.models import Tarif

from .models import Decompte
from .services import creer_decompte, valider_decompte

User = get_user_model()


def _dt(y, m, d, h=0):
    return timezone.make_aware(datetime(y, m, d, h, 0, 0))


class BaseDecompteViewTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='dec_viewer', password='TestPassword2026!'
        )
        for codename in ['add_decompte', 'change_decompte', 'view_decompte']:
            self.user.user_permissions.add(
                Permission.objects.get(
                    codename=codename, content_type__app_label='decomptes'
                )
            )
        self.agent = Agent.objects.create(
            matricule='AG-D-001', nom='Rabe', prenoms='Marie'
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


class DecompteListViewTests(BaseDecompteViewTest):

    def test_requires_login(self):
        r = self.client.get(reverse('decomptes:list'))
        self.assertEqual(r.status_code, 302)

    def test_requires_view_permission(self):
        u = User.objects.create_user(username='noperm_d', password='x')
        self.client.login(username='noperm_d', password='x')
        r = self.client.get(reverse('decomptes:list'))
        self.assertEqual(r.status_code, 403)

    def test_empty_list_ok(self):
        self.client.login(username='dec_viewer', password='TestPassword2026!')
        r = self.client.get(reverse('decomptes:list'))
        self.assertEqual(r.status_code, 200)


class DecompteCreateViewTests(BaseDecompteViewTest):

    def test_create_with_garde(self):
        self._garde(6)
        self.client.login(username='dec_viewer', password='TestPassword2026!')
        r = self.client.post(reverse('decomptes:create'), {
            'agent': self.agent.pk,
            'annee': 2026,
            'mois': 6,
        }, follow=True)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Decompte.objects.count(), 1)
        d = Decompte.objects.first()
        self.assertEqual(d.montant_total, Decimal('15000.00'))
        self.assertEqual(d.statut, Decompte.STATUT_BROUILLON)

    def test_create_duplicate_refused(self):
        self._garde(6)
        creer_decompte(self.agent, 2026, 6, self.user)
        self.client.login(username='dec_viewer', password='TestPassword2026!')
        r = self.client.post(reverse('decomptes:create'), {
            'agent': self.agent.pk,
            'annee': 2026,
            'mois': 6,
        })
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Decompte.objects.count(), 1)


class DecompteDetailViewTests(BaseDecompteViewTest):

    def test_detail_accessible(self):
        self._garde(6)
        d, _ = creer_decompte(self.agent, 2026, 6, self.user)
        self.client.login(username='dec_viewer', password='TestPassword2026!')
        r = self.client.get(reverse('decomptes:detail', args=[d.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, '15000')


class DecompteValiderViewTests(BaseDecompteViewTest):

    def test_valider_ok(self):
        self._garde(6)
        d, _ = creer_decompte(self.agent, 2026, 6, self.user)
        self.client.login(username='dec_viewer', password='TestPassword2026!')
        r = self.client.post(reverse('decomptes:valider', args=[d.pk]))
        self.assertEqual(r.status_code, 302)
        d.refresh_from_db()
        self.assertEqual(d.statut, Decompte.STATUT_VALIDE)
        self.assertEqual(d.id_utilisateur_validateur, self.user)

    def test_valider_double_refuse(self):
        self._garde(6)
        d, _ = creer_decompte(self.agent, 2026, 6, self.user)
        valider_decompte(d, self.user)
        self.client.login(username='dec_viewer', password='TestPassword2026!')
        r = self.client.post(reverse('decomptes:valider', args=[d.pk]))
        self.assertEqual(r.status_code, 200)
        d.refresh_from_db()
        self.assertEqual(d.statut, Decompte.STATUT_VALIDE)
