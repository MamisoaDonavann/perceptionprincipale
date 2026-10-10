"""
Tests CRUD missions + participations.
"""

from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from agents.models import Agent

from .models import Mission, ParticipationMission

User = get_user_model()


def _dt(y, m, d, h=0, mn=0):
    return timezone.make_aware(datetime(y, m, d, h, mn, 0))


class BaseMissionTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='mission_user', password='TestPassword2026!'
        )
        for codename in [
            'add_mission', 'change_mission', 'view_mission',
            'add_participationmission', 'change_participationmission',
            'view_participationmission',
        ]:
            self.user.user_permissions.add(
                Permission.objects.get(
                    codename=codename, content_type__app_label='missions'
                )
            )
        self.mission = Mission.objects.create(
            numero_officiel='M-2026-001',
            libelle='Mission test',
            date_debut=_dt(2026, 6, 1, 8),
            date_fin=_dt(2026, 6, 30, 18),
        )
        self.agent = Agent.objects.create(
            matricule='AG-M-001', nom='Rakoto', prenoms='Jean'
        )


class MissionListViewTests(BaseMissionTest):

    def test_requires_login(self):
        r = self.client.get(reverse('missions:list'))
        self.assertEqual(r.status_code, 302)

    def test_requires_view_permission(self):
        u = User.objects.create_user(username='noperm', password='x')
        self.client.login(username='noperm', password='x')
        r = self.client.get(reverse('missions:list'))
        self.assertEqual(r.status_code, 403)

    def test_accessible_with_permission(self):
        self.client.login(username='mission_user', password='TestPassword2026!')
        r = self.client.get(reverse('missions:list'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'M-2026-001')

    def test_search_filters(self):
        self.client.login(username='mission_user', password='TestPassword2026!')
        r = self.client.get(reverse('missions:list'), {'q': 'M-2026-001'})
        self.assertContains(r, 'M-2026-001')

        r = self.client.get(reverse('missions:list'), {'q': 'INEXISTANT'})
        self.assertNotContains(r, 'M-2026-001')

    def test_filter_statut(self):
        self.client.login(username='mission_user', password='TestPassword2026!')
        r = self.client.get(reverse('missions:list'), {'statut': 'PLANIFIEE'})
        self.assertContains(r, 'M-2026-001')

        r = self.client.get(reverse('missions:list'), {'statut': 'TERMINEE'})
        self.assertNotContains(r, 'M-2026-001')


class MissionDetailViewTests(BaseMissionTest):

    def test_detail_accessible(self):
        self.client.login(username='mission_user', password='TestPassword2026!')
        r = self.client.get(reverse('missions:detail', args=[self.mission.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Mission test')

    def test_404_unknown(self):
        self.client.login(username='mission_user', password='TestPassword2026!')
        r = self.client.get(reverse('missions:detail', args=[99999]))
        self.assertEqual(r.status_code, 404)


class MissionCreateViewTests(BaseMissionTest):

    def test_create_success(self):
        self.client.login(username='mission_user', password='TestPassword2026!')
        r = self.client.post(reverse('missions:create'), {
            'numero_officiel': 'M-2026-002',
            'libelle': 'Mission 2',
            'date_debut': '2026-07-01T08:00',
            'date_fin': '2026-07-05T18:00',
            'statut': 'PLANIFIEE',
        })
        self.assertEqual(r.status_code, 302)
        self.assertTrue(Mission.objects.filter(numero_officiel='M-2026-002').exists())


class MissionUpdateViewTests(BaseMissionTest):

    def test_update_success(self):
        self.client.login(username='mission_user', password='TestPassword2026!')
        r = self.client.post(reverse('missions:update', args=[self.mission.pk]), {
            'numero_officiel': 'M-2026-001',
            'libelle': 'Mission modifiée',
            'date_debut': '2026-06-01T08:00',
            'date_fin': '2026-06-30T18:00',
            'statut': 'EN_COURS',
        })
        self.assertEqual(r.status_code, 302)
        self.mission.refresh_from_db()
        self.assertEqual(self.mission.libelle, 'Mission modifiée')
        self.assertEqual(self.mission.statut, 'EN_COURS')


class ParticipationViewTests(BaseMissionTest):

    def test_add_participation(self):
        self.client.login(username='mission_user', password='TestPassword2026!')
        r = self.client.post(
            reverse('missions:participation_create', args=[self.mission.pk]),
            {
                'agent': self.agent.pk,
                'date_debut_participation': '2026-06-05T08:00',
                'date_fin_participation': '2026-06-10T18:00',
            }
        )
        self.assertEqual(r.status_code, 302)
        self.assertTrue(
            ParticipationMission.objects.filter(
                mission=self.mission, agent=self.agent
            ).exists()
        )

    def test_add_participation_out_of_range_refused(self):
        self.client.login(username='mission_user', password='TestPassword2026!')
        self.client.post(
            reverse('missions:participation_create', args=[self.mission.pk]),
            {
                'agent': self.agent.pk,
                'date_debut_participation': '2025-01-01T08:00',
                'date_fin_participation': '2025-01-05T18:00',
            }
        )
        self.assertFalse(
            ParticipationMission.objects.filter(
                mission=self.mission, agent=self.agent
            ).exists()
        )

    def test_remove_participation(self):
        p = ParticipationMission.objects.create(
            mission=self.mission, agent=self.agent,
            date_debut_participation=_dt(2026, 6, 5, 8),
            date_fin_participation=_dt(2026, 6, 10, 18),
        )
        self.client.login(username='mission_user', password='TestPassword2026!')
        r = self.client.post(
            reverse('missions:participation_delete', args=[self.mission.pk, p.pk])
        )
        self.assertEqual(r.status_code, 302)
        self.assertFalse(
            ParticipationMission.objects.filter(pk=p.pk).exists()
        )

    def test_remove_participation_requires_post(self):
        p = ParticipationMission.objects.create(
            mission=self.mission, agent=self.agent,
            date_debut_participation=_dt(2026, 6, 5, 8),
            date_fin_participation=_dt(2026, 6, 10, 18),
        )
        self.client.login(username='mission_user', password='TestPassword2026!')
        r = self.client.get(
            reverse('missions:participation_delete', args=[self.mission.pk, p.pk])
        )
        self.assertEqual(r.status_code, 405)
