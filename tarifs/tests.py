"""
Tests CRUD tarifs.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from agents.models import Agent
from gardes.models import Garde

from .models import Tarif

User = get_user_model()


class BaseTarifTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='tarif_user',
            password='TestPassword2026!',
        )
        for codename in ['add_tarif', 'change_tarif', 'view_tarif']:
            self.user.user_permissions.add(
                Permission.objects.get(
                    codename=codename,
                    content_type__app_label='tarifs',
                )
            )
        self.tarif = Tarif.objects.create(
            montant_partiel=Decimal('15000.00'),
            date_debut_validite=date(2026, 1, 1),
            id_utilisateur_createur=self.user,
        )


class TarifListViewTests(BaseTarifTest):

    def test_requires_login(self):
        response = self.client.get(reverse('tarifs:list'))
        self.assertEqual(response.status_code, 302)

    def test_requires_view_permission(self):
        u = User.objects.create_user(username='noperm', password='x')
        self.client.login(username='noperm', password='x')
        response = self.client.get(reverse('tarifs:list'))
        self.assertEqual(response.status_code, 403)

    def test_accessible_with_permission(self):
        self.client.login(username='tarif_user', password='TestPassword2026!')
        response = self.client.get(reverse('tarifs:list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '15000')

    def test_filter_actif(self):
        Tarif.objects.create(
            montant_partiel=Decimal('20000.00'),
            date_debut_validite=date(2026, 6, 1),
            actif=False,
            id_utilisateur_createur=self.user,
        )
        self.client.login(username='tarif_user', password='TestPassword2026!')
        response = self.client.get(reverse('tarifs:list'), {'actif': '1'})
        self.assertContains(response, '15000')

        response = self.client.get(reverse('tarifs:list'), {'actif': '0'})
        self.assertContains(response, '20000')


class TarifDetailViewTests(BaseTarifTest):

    def test_accessible(self):
        self.client.login(username='tarif_user', password='TestPassword2026!')
        response = self.client.get(reverse('tarifs:detail', args=[self.tarif.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '15000')

    def test_404_unknown(self):
        self.client.login(username='tarif_user', password='TestPassword2026!')
        response = self.client.get(reverse('tarifs:detail', args=[99999]))
        self.assertEqual(response.status_code, 404)


class TarifCreateViewTests(BaseTarifTest):

    def test_create_success(self):
        self.client.login(username='tarif_user', password='TestPassword2026!')
        response = self.client.post(reverse('tarifs:create'), {
            'montant_partiel': '25000.00',
            'date_debut_validite': '2026-07-01',
            'date_fin_validite': '',
            'actif': 'on',
            'motif_modification': '',
        })
        self.assertEqual(response.status_code, 302)
        t = Tarif.objects.get(montant_partiel=Decimal('25000.00'))
        self.assertEqual(t.id_utilisateur_createur, self.user)

    def test_create_invalid_dates(self):
        self.client.login(username='tarif_user', password='TestPassword2026!')
        response = self.client.post(reverse('tarifs:create'), {
            'montant_partiel': '25000.00',
            'date_debut_validite': '2026-07-01',
            'date_fin_validite': '2026-06-01',
            'actif': 'on',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'postérieure ou égale')


class TarifUpdateViewTests(BaseTarifTest):

    def test_update_unused_tarif(self):
        self.client.login(username='tarif_user', password='TestPassword2026!')
        response = self.client.post(
            reverse('tarifs:update', args=[self.tarif.pk]),
            {
                'montant_partiel': '18000.00',
                'date_debut_validite': '2026-01-01',
                'date_fin_validite': '',
                'actif': 'on',
                'motif_modification': 'Ajustement',
            }
        )
        self.assertEqual(response.status_code, 302)
        self.tarif.refresh_from_db()
        self.assertEqual(self.tarif.montant_partiel, Decimal('18000.00'))

    def test_update_used_tarif_refused(self):
        agent = Agent.objects.create(
            matricule='AG-TARIF-001', nom='X', prenoms='Y'
        )
        from django.utils import timezone
        from datetime import datetime
        debut = timezone.make_aware(datetime(2026, 2, 1, 6, 0))
        fin = timezone.make_aware(datetime(2026, 2, 1, 18, 0))
        Garde.objects.create(
            agent=agent, tarif=self.tarif,
            date_heure_debut=debut, date_heure_fin=fin,
            duree_minutes=720, nombre_partiels=1, conforme=True,
            id_utilisateur_saisie=self.user,
        )

        self.client.login(username='tarif_user', password='TestPassword2026!')
        response = self.client.get(reverse('tarifs:update', args=[self.tarif.pk]))
        self.assertEqual(response.status_code, 302)  # redirigé vers détail
        self.tarif.refresh_from_db()
        self.assertEqual(self.tarif.montant_partiel, Decimal('15000.00'))


class TarifToggleViewTests(BaseTarifTest):

    def test_toggle_desactive(self):
        self.client.login(username='tarif_user', password='TestPassword2026!')
        response = self.client.post(
            reverse('tarifs:toggle_actif', args=[self.tarif.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.tarif.refresh_from_db()
        self.assertFalse(self.tarif.actif)

    def test_toggle_requires_post(self):
        self.client.login(username='tarif_user', password='TestPassword2026!')
        response = self.client.get(
            reverse('tarifs:toggle_actif', args=[self.tarif.pk])
        )
        self.assertEqual(response.status_code, 405)
