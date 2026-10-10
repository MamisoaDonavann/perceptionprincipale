"""
Tests CRUD gardes (via services).
"""

from datetime import date, datetime, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from agents.models import Agent
from missions.models import Mission
from tarifs.models import Tarif

from .models import Garde

User = get_user_model()


def _dt(y, m, d, h=0, mn=0):
    return timezone.make_aware(datetime(y, m, d, h, mn, 0))


class BaseGardeViewTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='garde_viewer', password='TestPassword2026!'
        )
        for codename in ['add_garde', 'change_garde', 'view_garde']:
            self.user.user_permissions.add(
                Permission.objects.get(
                    codename=codename, content_type__app_label='gardes'
                )
            )
        # Permission custom annuler_garde (créée normalement par setup_groups)
        from django.contrib.contenttypes.models import ContentType
        from gardes.models import Garde
        ct = ContentType.objects.get_for_model(Garde)
        perm_annuler, _ = Permission.objects.get_or_create(
            content_type=ct,
            codename='annuler_garde',
            defaults={'name': "Peut annuler une garde"},
        )
        self.user.user_permissions.add(perm_annuler)
        self.agent = Agent.objects.create(
            matricule='AG-G-001', nom='Rakoto', prenoms='Jean'
        )
        self.tarif = Tarif.objects.create(
            montant_partiel=Decimal('15000.00'),
            date_debut_validite=date(2025, 1, 1),
            id_utilisateur_createur=self.user,
        )
        self.mission = Mission.objects.create(
            libelle='Mission G',
            date_debut=_dt(2026, 1, 1, 0),
            date_fin=_dt(2026, 12, 31, 23, 59),
        )


class GardeListViewTests(BaseGardeViewTest):

    def test_requires_login(self):
        r = self.client.get(reverse('gardes:list'))
        self.assertEqual(r.status_code, 302)

    def test_requires_view_permission(self):
        u = User.objects.create_user(username='noperm_g', password='x')
        self.client.login(username='noperm_g', password='x')
        r = self.client.get(reverse('gardes:list'))
        self.assertEqual(r.status_code, 403)

    def test_empty_list_accessible(self):
        self.client.login(username='garde_viewer', password='TestPassword2026!')
        r = self.client.get(reverse('gardes:list'))
        self.assertEqual(r.status_code, 200)

    def test_filter_conforme(self):
        Garde.objects.create(
            agent=self.agent, tarif=self.tarif,
            date_heure_debut=_dt(2026, 6, 1, 6),
            date_heure_fin=_dt(2026, 6, 1, 18),
            duree_minutes=720, nombre_partiels=1, conforme=True,
            id_utilisateur_saisie=self.user,
        )
        self.client.login(username='garde_viewer', password='TestPassword2026!')
        r = self.client.get(reverse('gardes:list'), {'conforme': '1'})
        self.assertContains(r, 'AG-G-001')


class GardeCreateViewTests(BaseGardeViewTest):

    def test_create_requires_add_permission(self):
        u = User.objects.create_user(username='viewonly_g', password='x')
        u.user_permissions.add(Permission.objects.get(
            codename='view_garde', content_type__app_label='gardes'
        ))
        self.client.login(username='viewonly_g', password='x')
        r = self.client.get(reverse('gardes:create'))
        self.assertEqual(r.status_code, 403)

    def test_create_garde_12h_success(self):
        self.client.login(username='garde_viewer', password='TestPassword2026!')
        r = self.client.post(reverse('gardes:create'), {
            'agent': self.agent.pk,
            'mission': self.mission.pk,
            'tarif': self.tarif.pk,
            'date_heure_debut': '2026-06-01T06:00',
            'date_heure_fin': '2026-06-01T18:00',
            'observation': '',
        }, follow=True)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Garde.objects.count(), 1)
        g = Garde.objects.first()
        self.assertEqual(g.nombre_partiels, 1)
        self.assertTrue(g.conforme)

    def test_create_garde_non_conforme_allowed(self):
        self.client.login(username='garde_viewer', password='TestPassword2026!')
        self.client.post(reverse('gardes:create'), {
            'agent': self.agent.pk,
            'mission': '',
            'tarif': self.tarif.pk,
            'date_heure_debut': '2026-06-01T06:00',
            'date_heure_fin': '2026-06-01T12:00',
        })
        self.assertEqual(Garde.objects.count(), 1)
        g = Garde.objects.first()
        self.assertFalse(g.conforme)
        self.assertIsNone(g.nombre_partiels)

    def test_create_garde_duration_zero_refused(self):
        self.client.login(username='garde_viewer', password='TestPassword2026!')
        self.client.post(reverse('gardes:create'), {
            'agent': self.agent.pk,
            'tarif': self.tarif.pk,
            'date_heure_debut': '2026-06-01T06:00',
            'date_heure_fin': '2026-06-01T06:00',
        })
        self.assertEqual(Garde.objects.count(), 0)


class GardeDetailViewTests(BaseGardeViewTest):

    def test_detail_accessible(self):
        g = Garde.objects.create(
            agent=self.agent, tarif=self.tarif,
            date_heure_debut=_dt(2026, 6, 1, 6),
            date_heure_fin=_dt(2026, 6, 1, 18),
            duree_minutes=720, nombre_partiels=1, conforme=True,
            id_utilisateur_saisie=self.user,
        )
        self.client.login(username='garde_viewer', password='TestPassword2026!')
        r = self.client.get(reverse('gardes:detail', args=[g.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'AG-G-001')


class GardeAnnulerViewTests(BaseGardeViewTest):

    def test_annuler_garde_with_motif(self):
        g = Garde.objects.create(
            agent=self.agent, tarif=self.tarif,
            date_heure_debut=_dt(2026, 6, 1, 6),
            date_heure_fin=_dt(2026, 6, 1, 18),
            duree_minutes=720, nombre_partiels=1, conforme=True,
            id_utilisateur_saisie=self.user,
        )
        self.client.login(username='garde_viewer', password='TestPassword2026!')
        r = self.client.post(
            reverse('gardes:annuler', args=[g.pk]),
            {'motif': 'Erreur de saisie'}
        )
        self.assertEqual(r.status_code, 302)
        g.refresh_from_db()
        self.assertEqual(g.statut, Garde.STATUT_ANNULEE)

    def test_annuler_sans_motif_refuse(self):
        g = Garde.objects.create(
            agent=self.agent, tarif=self.tarif,
            date_heure_debut=_dt(2026, 6, 1, 6),
            date_heure_fin=_dt(2026, 6, 1, 18),
            duree_minutes=720, nombre_partiels=1, conforme=True,
            id_utilisateur_saisie=self.user,
        )
        self.client.login(username='garde_viewer', password='TestPassword2026!')
        r = self.client.post(reverse('gardes:annuler', args=[g.pk]), {'motif': ''})
        self.assertEqual(r.status_code, 200)
        g.refresh_from_db()
        self.assertEqual(g.statut, Garde.STATUT_VALIDEE)
