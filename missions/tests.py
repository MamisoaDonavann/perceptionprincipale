from datetime import datetime, timezone as dt_timezone

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase

from agents.models import Agent
from .models import Mission, ParticipationMission


class MissionModelTests(TestCase):
    """Tests techniques minimaux. Aucune donnée administrative réelle."""

    def test_plusieurs_missions_sans_numero_officiel(self):
        Mission.objects.create(
            numero_officiel=None,
            libelle='M1',
            date_debut=datetime(2026, 1, 1, tzinfo=dt_timezone.utc),
            date_fin=datetime(2026, 1, 2, tzinfo=dt_timezone.utc),
        )
        Mission.objects.create(
            numero_officiel=None,
            libelle='M2',
            date_debut=datetime(2026, 2, 1, tzinfo=dt_timezone.utc),
            date_fin=datetime(2026, 2, 2, tzinfo=dt_timezone.utc),
        )
        self.assertEqual(Mission.objects.filter(numero_officiel__isnull=True).count(), 2)

    def test_numero_officiel_chaine_vide_normalisee(self):
        m = Mission.objects.create(
            numero_officiel='',
            libelle='M3',
            date_debut=datetime(2026, 1, 1, tzinfo=dt_timezone.utc),
            date_fin=datetime(2026, 1, 2, tzinfo=dt_timezone.utc),
        )
        self.assertIsNone(m.numero_officiel)

    def test_date_fin_anterieure_refusee(self):
        with self.assertRaises(IntegrityError):
            Mission.objects.create(
                libelle='M4',
                date_debut=datetime(2026, 6, 1, tzinfo=dt_timezone.utc),
                date_fin=datetime(2026, 1, 1, tzinfo=dt_timezone.utc),
            )


class ParticipationMissionModelTests(TestCase):

    def setUp(self):
        self.mission = Mission.objects.create(
            libelle='M-TEST',
            date_debut=datetime(2026, 1, 1, tzinfo=dt_timezone.utc),
            date_fin=datetime(2026, 12, 31, tzinfo=dt_timezone.utc),
        )
        self.agent = Agent.objects.create(
            matricule='TEST-M1', nom='N', prenoms='P'
        )

    def test_unicite_mission_agent(self):
        ParticipationMission.objects.create(
            mission=self.mission,
            agent=self.agent,
            date_debut_participation=datetime(2026, 1, 1, tzinfo=dt_timezone.utc),
            date_fin_participation=datetime(2026, 1, 10, tzinfo=dt_timezone.utc),
        )
        with self.assertRaises(IntegrityError):
            ParticipationMission.objects.create(
                mission=self.mission,
                agent=self.agent,
                date_debut_participation=datetime(2026, 2, 1, tzinfo=dt_timezone.utc),
                date_fin_participation=datetime(2026, 2, 10, tzinfo=dt_timezone.utc),
            )

    def test_clean_refuse_participation_hors_mission(self):
        p = ParticipationMission(
            mission=self.mission,
            agent=self.agent,
            date_debut_participation=datetime(2025, 12, 1, tzinfo=dt_timezone.utc),
            date_fin_participation=datetime(2026, 1, 10, tzinfo=dt_timezone.utc),
        )
        with self.assertRaises(ValidationError):
            p.clean()

    def test_clean_accepte_participation_dans_mission(self):
        p = ParticipationMission(
            mission=self.mission,
            agent=self.agent,
            date_debut_participation=datetime(2026, 1, 1, tzinfo=dt_timezone.utc),
            date_fin_participation=datetime(2026, 1, 10, tzinfo=dt_timezone.utc),
        )
        p.clean()  # Ne doit pas lever d'exception
