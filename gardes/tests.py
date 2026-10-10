from datetime import date, datetime, timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from agents.models import Agent
from audit.models import JournalAudit
from missions.models import Mission
from tarifs.models import Tarif

from .models import Garde
from .services import creer_garde, annuler_garde

User = get_user_model()


def _dt(y, m, d, h, mn=0):
    """Crée un datetime aware (fuseau courant)."""
    return timezone.make_aware(datetime(y, m, d, h, mn))


class BaseGardeTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='garde_user', password='test_password_2026'
        )
        self.agent = Agent.objects.create(
            matricule='AG-001', nom='Nom', prenoms='Prenoms'
        )
        self.mission = Mission.objects.create(
            libelle='Mission test',
            date_debut=_dt(2026, 1, 1, 0),
            date_fin=_dt(2026, 12, 31, 23, 59),
        )
        # Tarif dont la période couvre largement les gardes testées (2026).
        self.tarif = Tarif.objects.create(
            montant_partiel='15000.00',
            date_debut_validite=date(2025, 1, 1),
            date_fin_validite=None,
            id_utilisateur_createur=self.user,
        )


class CalculDureeTests(BaseGardeTest):

    def test_garde_12h_conforme_1_partiel(self):
        garde, avert = creer_garde(
            user=self.user,
            agent=self.agent,
            date_heure_debut=_dt(2026, 6, 1, 6),
            date_heure_fin=_dt(2026, 6, 1, 18),
            tarif=self.tarif,
        )
        self.assertEqual(garde.duree_minutes, 720)
        self.assertEqual(garde.nombre_partiels, 1)
        self.assertTrue(garde.conforme)

    def test_garde_24h_conforme_2_partiels(self):
        garde, avert = creer_garde(
            user=self.user,
            agent=self.agent,
            date_heure_debut=_dt(2026, 6, 1, 6),
            date_heure_fin=_dt(2026, 6, 2, 6),
            tarif=self.tarif,
        )
        self.assertEqual(garde.duree_minutes, 1440)
        self.assertEqual(garde.nombre_partiels, 2)
        self.assertTrue(garde.conforme)

    def test_garde_traversant_minuit(self):
        garde, avert = creer_garde(
            user=self.user,
            agent=self.agent,
            date_heure_debut=_dt(2026, 6, 1, 18),
            date_heure_fin=_dt(2026, 6, 2, 18),
            tarif=self.tarif,
        )
        self.assertEqual(garde.duree_minutes, 1440)
        self.assertEqual(garde.nombre_partiels, 2)
        self.assertTrue(garde.conforme)

    def test_duree_non_multiple_12h(self):
        garde, avert = creer_garde(
            user=self.user,
            agent=self.agent,
            date_heure_debut=_dt(2026, 6, 1, 6),
            date_heure_fin=_dt(2026, 6, 1, 12),
            tarif=self.tarif,
        )
        self.assertEqual(garde.duree_minutes, 360)
        self.assertIsNone(garde.nombre_partiels)
        self.assertFalse(garde.conforme)
        self.assertNotEqual(garde.motif_anomalie, "")

    def test_duree_nulle_refusee(self):
        with self.assertRaises(ValidationError):
            creer_garde(
                user=self.user,
                agent=self.agent,
                date_heure_debut=_dt(2026, 6, 1, 6),
                date_heure_fin=_dt(2026, 6, 1, 6),
                tarif=self.tarif,
            )

    def test_duree_negative_refusee(self):
        with self.assertRaises(ValidationError):
            creer_garde(
                user=self.user,
                agent=self.agent,
                date_heure_debut=_dt(2026, 6, 1, 18),
                date_heure_fin=_dt(2026, 6, 1, 6),
                tarif=self.tarif,
            )

    def test_secondes_residuelles_refusees(self):
        with self.assertRaises(ValidationError):
            creer_garde(
                user=self.user,
                agent=self.agent,
                date_heure_debut=_dt(2026, 6, 1, 6),
                date_heure_fin=_dt(2026, 6, 1, 18) + timedelta(seconds=30),
                tarif=self.tarif,
            )


class TarifApplicableTests(BaseGardeTest):

    def test_tarif_unique_applicable(self):
        garde, avert = creer_garde(
            user=self.user,
            agent=self.agent,
            date_heure_debut=_dt(2026, 6, 1, 6),
            date_heure_fin=_dt(2026, 6, 1, 18),
        )
        self.assertEqual(garde.tarif_id, self.tarif.pk)

    def test_aucun_tarif_applicable(self):
        Tarif.objects.all().delete()
        with self.assertRaises(ValidationError):
            creer_garde(
                user=self.user,
                agent=self.agent,
                date_heure_debut=_dt(2026, 6, 1, 6),
                date_heure_fin=_dt(2026, 6, 1, 18),
            )

    def test_plusieurs_tarifs_applicables(self):
        # Deuxième tarif qui couvre aussi juin 2026 -> conflit
        Tarif.objects.create(
            montant_partiel='20000.00',
            date_debut_validite=date(2025, 6, 1),
            date_fin_validite=None,
            id_utilisateur_createur=self.user,
        )
        with self.assertRaises(ValidationError):
            creer_garde(
                user=self.user,
                agent=self.agent,
                date_heure_debut=_dt(2026, 6, 1, 6),
                date_heure_fin=_dt(2026, 6, 1, 18),
            )


class ChevauchementTests(BaseGardeTest):

    def test_chevauchement_signale_sans_bloquer(self):
        creer_garde(
            user=self.user,
            agent=self.agent,
            date_heure_debut=_dt(2026, 6, 1, 6),
            date_heure_fin=_dt(2026, 6, 1, 18),
            tarif=self.tarif,
        )
        garde2, avertissements = creer_garde(
            user=self.user,
            agent=self.agent,
            date_heure_debut=_dt(2026, 6, 1, 12),
            date_heure_fin=_dt(2026, 6, 1, 20),
            tarif=self.tarif,
        )
        self.assertIsNotNone(garde2.pk)
        self.assertTrue(len(avertissements) > 0)


class MissionFacultativeTests(BaseGardeTest):

    def test_garde_sans_mission(self):
        garde, avert = creer_garde(
            user=self.user,
            agent=self.agent,
            date_heure_debut=_dt(2026, 6, 1, 6),
            date_heure_fin=_dt(2026, 6, 1, 18),
            tarif=self.tarif,
            mission=None,
        )
        self.assertIsNone(garde.mission)


class AnnulationTests(BaseGardeTest):

    def test_annulation_controlee(self):
        garde, avert = creer_garde(
            user=self.user,
            agent=self.agent,
            date_heure_debut=_dt(2026, 6, 1, 6),
            date_heure_fin=_dt(2026, 6, 1, 18),
            tarif=self.tarif,
        )
        garde = annuler_garde(self.user, garde, motif="Erreur de saisie")
        self.assertEqual(garde.statut, Garde.STATUT_ANNULEE)

    def test_annulation_sans_motif_refusee(self):
        garde, avert = creer_garde(
            user=self.user,
            agent=self.agent,
            date_heure_debut=_dt(2026, 6, 1, 6),
            date_heure_fin=_dt(2026, 6, 1, 18),
            tarif=self.tarif,
        )
        with self.assertRaises(ValidationError):
            annuler_garde(self.user, garde, motif="")

    def test_annulation_double_refusee(self):
        garde, avert = creer_garde(
            user=self.user,
            agent=self.agent,
            date_heure_debut=_dt(2026, 6, 1, 6),
            date_heure_fin=_dt(2026, 6, 1, 18),
            tarif=self.tarif,
        )
        annuler_garde(self.user, garde, motif="Motif 1")
        with self.assertRaises(ValidationError):
            annuler_garde(self.user, garde, motif="Motif 2")


class JournalisationTests(BaseGardeTest):

    def test_creation_journalisee(self):
        creer_garde(
            user=self.user,
            agent=self.agent,
            date_heure_debut=_dt(2026, 6, 1, 6),
            date_heure_fin=_dt(2026, 6, 1, 18),
            tarif=self.tarif,
        )
        entries = JournalAudit.objects.filter(
            entite_concernee='gardes.Garde',
            action=JournalAudit.ACTION_CREATION,
        )
        self.assertEqual(entries.count(), 1)

    def test_annulation_journalisee(self):
        garde, avert = creer_garde(
            user=self.user,
            agent=self.agent,
            date_heure_debut=_dt(2026, 6, 1, 6),
            date_heure_fin=_dt(2026, 6, 1, 18),
            tarif=self.tarif,
        )
        annuler_garde(self.user, garde, motif="Test")
        entries = JournalAudit.objects.filter(
            entite_concernee='gardes.Garde',
            action=JournalAudit.ACTION_ANNULATION,
        )
        self.assertEqual(entries.count(), 1)


class ProtectionHistoriqueTests(BaseGardeTest):

    def test_suppression_agent_refusee(self):
        creer_garde(
            user=self.user,
            agent=self.agent,
            date_heure_debut=_dt(2026, 6, 1, 6),
            date_heure_fin=_dt(2026, 6, 1, 18),
            tarif=self.tarif,
        )
        with self.assertRaises(Exception):
            self.agent.delete()

    def test_suppression_tarif_refusee(self):
        creer_garde(
            user=self.user,
            agent=self.agent,
            date_heure_debut=_dt(2026, 6, 1, 6),
            date_heure_fin=_dt(2026, 6, 1, 18),
            tarif=self.tarif,
        )
        with self.assertRaises(Exception):
            self.tarif.delete()
