from datetime import date

from django.db import IntegrityError
from django.test import TestCase

from core.models import Unite
from .models import Agent, AffectationAgent


class AgentModelTests(TestCase):
    """Tests techniques minimaux. Aucune donnée administrative réelle."""

    def test_matricule_unique(self):
        Agent.objects.create(matricule='TEST-001', nom='N1', prenoms='P1')
        with self.assertRaises(IntegrityError):
            Agent.objects.create(matricule='TEST-001', nom='N2', prenoms='P2')

    def test_cin_unique_si_renseigne(self):
        Agent.objects.create(matricule='TEST-002', nom='N1', prenoms='P1', cin='CIN-001')
        with self.assertRaises(IntegrityError):
            Agent.objects.create(matricule='TEST-003', nom='N2', prenoms='P2', cin='CIN-001')

    def test_cin_multiple_null_autorise(self):
        Agent.objects.create(matricule='TEST-004', nom='N1', prenoms='P1', cin=None)
        Agent.objects.create(matricule='TEST-005', nom='N2', prenoms='P2', cin=None)
        self.assertEqual(Agent.objects.filter(cin__isnull=True).count(), 2)


class AffectationAgentModelTests(TestCase):
    """Tests de la contrainte date_fin >= date_debut."""

    def setUp(self):
        self.agent = Agent.objects.create(
            matricule='TEST-A1', nom='N', prenoms='P'
        )
        self.unite = Unite.objects.create(code='U-TEST', libelle='Unité de test')

    def test_date_fin_valide(self):
        AffectationAgent.objects.create(
            agent=self.agent,
            unite=self.unite,
            date_debut=date(2026, 1, 1),
            date_fin=date(2026, 6, 30),
        )
        self.assertEqual(AffectationAgent.objects.count(), 1)

    def test_date_fin_null_autorisee(self):
        AffectationAgent.objects.create(
            agent=self.agent,
            unite=self.unite,
            date_debut=date(2026, 1, 1),
            date_fin=None,
        )
        self.assertEqual(AffectationAgent.objects.count(), 1)

    def test_date_fin_anterieure_refusee(self):
        with self.assertRaises(IntegrityError):
            AffectationAgent.objects.create(
                agent=self.agent,
                unite=self.unite,
                date_debut=date(2026, 6, 1),
                date_fin=date(2026, 1, 1),
            )
