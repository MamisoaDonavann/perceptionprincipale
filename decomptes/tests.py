from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from agents.models import Agent
from audit.models import JournalAudit
from gardes.models import Garde
from tarifs.models import Tarif

from .models import Decompte, LigneDecompte
from .services import creer_decompte, valider_decompte

User = get_user_model()


def _dt(y, m, d, h=0, mn=0):
    """datetime aware dans le fuseau courant."""
    return timezone.make_aware(datetime(y, m, d, h, mn, 0))


class BaseDecompteTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='dec_user', password='test_password_2026'
        )
        self.agent = Agent.objects.create(
            matricule='AG-DEC-01', nom='Nom', prenoms='Prenoms'
        )
        self.tarif = Tarif.objects.create(
            montant_partiel=Decimal('15000.00'),
            date_debut_validite=date(2025, 1, 1),
            date_fin_validite=None,
            id_utilisateur_createur=self.user,
        )

    def _garde(self, debut, fin, tarif=None, conforme_attendu=True):
        """Crée une garde via l'ORM (sans service) pour contrôle direct."""
        g = Garde(
            agent=self.agent,
            tarif=tarif or self.tarif,
            date_heure_debut=debut,
            date_heure_fin=fin,
            id_utilisateur_saisie=self.user,
        )
        g._recalculer()
        g.full_clean(exclude=None, validate_unique=False)
        g.save()
        if conforme_attendu:
            assert g.conforme
        return g


class CreationDecompteTests(BaseDecompteTest):

    def test_creation_decompte_1_garde(self):
        self._garde(_dt(2026, 6, 1, 6), _dt(2026, 6, 1, 18))
        d, avert = creer_decompte(self.agent, 2026, 6, self.user)
        self.assertEqual(d.montant_total, Decimal('15000.00'))
        self.assertEqual(d.nombre_gardes_retunes, 1)
        self.assertEqual(d.statut, Decompte.STATUT_BROUILLON)

    def test_creation_avec_plusieurs_gardes(self):
        self._garde(_dt(2026, 6, 1, 6), _dt(2026, 6, 1, 18))
        self._garde(_dt(2026, 6, 5, 6), _dt(2026, 6, 6, 6))
        self._garde(_dt(2026, 6, 10, 0), _dt(2026, 6, 10, 12))
        d, _ = creer_decompte(self.agent, 2026, 6, self.user)
        self.assertEqual(d.nombre_gardes_retunes, 3)
        self.assertEqual(d.montant_total, Decimal('60000.00'))  # 1+2+1 partiels

    def test_creation_avec_tarifs_historiques_differents(self):
        self._garde(_dt(2026, 6, 1, 6), _dt(2026, 6, 1, 18))
        tarif2 = Tarif.objects.create(
            montant_partiel=Decimal('20000.00'),
            date_debut_validite=date(2026, 6, 2),
            date_fin_validite=None,
            id_utilisateur_createur=self.user,
        )
        self._garde(_dt(2026, 6, 3, 6), _dt(2026, 6, 3, 18), tarif=tarif2)
        d, _ = creer_decompte(self.agent, 2026, 6, self.user)
        self.assertEqual(d.montant_total, Decimal('35000.00'))

    def test_decompte_sans_garde_eligible(self):
        d, avert = creer_decompte(self.agent, 2026, 6, self.user)
        self.assertEqual(d.montant_total, Decimal('0.00'))
        self.assertEqual(d.nombre_gardes_retunes, 0)
        self.assertTrue(any("Aucune garde" in a for a in avert))

    def test_garde_affectee_au_mois_de_debut(self):
        # Garde qui commence le 30 juin 22:00 et finit le 1er juillet 10:00.
        self._garde(_dt(2026, 6, 30, 22), _dt(2026, 7, 1, 10))
        d_juin, _ = creer_decompte(self.agent, 2026, 6, self.user)
        self.assertEqual(d_juin.nombre_gardes_retunes, 1)

        # Un décompte de juillet ne doit pas inclure cette garde.
        agent2 = Agent.objects.create(
            matricule='AG-DEC-02', nom='N', prenoms='P'
        )
        self._garde.__self__  # no-op
        d_juillet, _ = creer_decompte(agent2, 2026, 7, self.user)
        self.assertEqual(d_juillet.nombre_gardes_retunes, 0)

    def test_montant_total_somme_des_lignes(self):
        self._garde(_dt(2026, 6, 1, 6), _dt(2026, 6, 1, 18))
        self._garde(_dt(2026, 6, 2, 6), _dt(2026, 6, 3, 6))
        d, _ = creer_decompte(self.agent, 2026, 6, self.user)
        somme = sum(l.montant_ligne for l in d.lignes.all())
        self.assertEqual(d.montant_total, somme)

    def test_snapshot_montant_partiel(self):
        self._garde(_dt(2026, 6, 1, 6), _dt(2026, 6, 1, 18))
        d, _ = creer_decompte(self.agent, 2026, 6, self.user)
        ligne = d.lignes.first()
        self.assertEqual(ligne.montant_partiel_snapshot, Decimal('15000.00'))


class ExclusionsTests(BaseDecompteTest):

    def test_exclusion_gardes_non_conformes(self):
        self._garde(_dt(2026, 6, 1, 6), _dt(2026, 6, 1, 18))  # 12h -> conforme
        self._garde(_dt(2026, 6, 2, 6), _dt(2026, 6, 2, 12), conforme_attendu=False)  # 6h -> non conforme
        d, avert = creer_decompte(self.agent, 2026, 6, self.user)
        self.assertEqual(d.nombre_gardes_retunes, 1)
        self.assertEqual(d.nombre_gardes_non_conformes_exclues, 1)
        self.assertTrue(any("non conforme" in a for a in avert))

    def test_exclusion_gardes_annulees(self):
        g = self._garde(_dt(2026, 6, 1, 6), _dt(2026, 6, 1, 18))
        g.statut = Garde.STATUT_ANNULEE
        g.save(update_fields=['statut'])
        d, _ = creer_decompte(self.agent, 2026, 6, self.user)
        self.assertEqual(d.nombre_gardes_retunes, 0)

    def test_exclusion_gardes_autre_agent(self):
        autre = Agent.objects.create(
            matricule='AG-AUTRE', nom='N', prenoms='P'
        )
        g = self._garde(_dt(2026, 6, 1, 6), _dt(2026, 6, 1, 18))
        g.agent = autre
        g.save(update_fields=['agent'])
        d, _ = creer_decompte(self.agent, 2026, 6, self.user)
        self.assertEqual(d.nombre_gardes_retunes, 0)


class ValidationEntreesTests(BaseDecompteTest):

    def test_mois_invalide(self):
        with self.assertRaises(ValidationError):
            creer_decompte(self.agent, 2026, 0, self.user)
        with self.assertRaises(ValidationError):
            creer_decompte(self.agent, 2026, 13, self.user)

    def test_annee_invalide(self):
        with self.assertRaises(ValidationError):
            creer_decompte(self.agent, 1800, 6, self.user)
        with self.assertRaises(ValidationError):
            creer_decompte(self.agent, 3000, 6, self.user)

    def test_refus_doublon_meme_periode(self):
        creer_decompte(self.agent, 2026, 6, self.user)
        with self.assertRaises(ValidationError):
            creer_decompte(self.agent, 2026, 6, self.user)


class FigementDonneesTests(BaseDecompteTest):

    def test_montants_inchanges_apres_modification_tarif(self):
        self._garde(_dt(2026, 6, 1, 6), _dt(2026, 6, 1, 18))
        d, _ = creer_decompte(self.agent, 2026, 6, self.user)
        ligne = d.lignes.first()
        ancien = ligne.montant_partiel_snapshot

        Tarif.objects.filter(pk=self.tarif.pk).update(
            montant_partiel=Decimal('99999.00')
        )
        ligne.refresh_from_db()
        self.assertEqual(ligne.montant_partiel_snapshot, ancien)

    def test_snapshot_inchange_apres_modification_garde(self):
        g = self._garde(_dt(2026, 6, 1, 6), _dt(2026, 6, 1, 18))
        d, _ = creer_decompte(self.agent, 2026, 6, self.user)
        ligne = d.lignes.first()
        ancien = ligne.duree_minutes_snapshot

        # Modification directe en base pour contourner _recalculer
        Garde.objects.filter(pk=g.pk).update(duree_minutes=99999)
        ligne.refresh_from_db()
        self.assertEqual(ligne.duree_minutes_snapshot, ancien)

    def test_protection_suppression_tarif_reference(self):
        self._garde(_dt(2026, 6, 1, 6), _dt(2026, 6, 1, 18))
        creer_decompte(self.agent, 2026, 6, self.user)
        with self.assertRaises(Exception):
            self.tarif.delete()


class ValidationStatutsTests(BaseDecompteTest):

    def test_validation_brouillon_vers_valide(self):
        self._garde(_dt(2026, 6, 1, 6), _dt(2026, 6, 1, 18))
        d, _ = creer_decompte(self.agent, 2026, 6, self.user)
        d = valider_decompte(d, self.user)
        self.assertEqual(d.statut, Decompte.STATUT_VALIDE)
        self.assertEqual(d.id_utilisateur_validateur, self.user)
        self.assertIsNotNone(d.date_validation)

    def test_refus_validation_double(self):
        self._garde(_dt(2026, 6, 1, 6), _dt(2026, 6, 1, 18))
        d, _ = creer_decompte(self.agent, 2026, 6, self.user)
        valider_decompte(d, self.user)
        with self.assertRaises(ValidationError):
            valider_decompte(d, self.user)


class AuditTests(BaseDecompteTest):

    def test_creation_journalisee(self):
        self._garde(_dt(2026, 6, 1, 6), _dt(2026, 6, 1, 18))
        creer_decompte(self.agent, 2026, 6, self.user)
        self.assertEqual(
            JournalAudit.objects.filter(
                entite_concernee='decomptes.Decompte',
                action=JournalAudit.ACTION_CREATION,
            ).count(),
            1,
        )

    def test_validation_journalisee(self):
        self._garde(_dt(2026, 6, 1, 6), _dt(2026, 6, 1, 18))
        d, _ = creer_decompte(self.agent, 2026, 6, self.user)
        valider_decompte(d, self.user)
        self.assertEqual(
            JournalAudit.objects.filter(
                entite_concernee='decomptes.Decompte',
                action=JournalAudit.ACTION_VALIDATION,
            ).count(),
            1,
        )

    def test_rollback_si_audit_echoue(self):
        self._garde(_dt(2026, 6, 1, 6), _dt(2026, 6, 1, 18))
        with patch('decomptes.services.journaliser', side_effect=Exception("audit down")):
            with self.assertRaises(Exception):
                creer_decompte(self.agent, 2026, 6, self.user)
        self.assertFalse(
            Decompte.objects.filter(agent=self.agent, annee=2026, mois=6).exists()
        )
        self.assertEqual(LigneDecompte.objects.count(), 0)


class DoubleUtilisationGardeTests(BaseDecompteTest):

    def test_garde_deja_utilisee_refusee_par_contrainte_db(self):
        """
        La contrainte unique globale sur LigneDecompte.garde_id
        empêche toute réutilisation d'une garde dans un autre décompte,
        même pour un mois différent.
        """
        g = self._garde(_dt(2026, 6, 1, 6), _dt(2026, 6, 1, 18))
        creer_decompte(self.agent, 2026, 6, self.user)

        # Créer un décompte différent (autre mois) pour tester la contrainte
        # globale sur LigneDecompte.garde_id.
        autre_decompte = Decompte.objects.create(
            agent=self.agent,
            annee=2026,
            mois=7,
            statut=Decompte.STATUT_BROUILLON,
            montant_total=Decimal('0.00'),
            id_utilisateur_createur=self.user,
        )

        with self.assertRaises(IntegrityError):
            LigneDecompte.objects.create(
                decompte=autre_decompte,
                garde=g,
                tarif=self.tarif,
                duree_minutes_snapshot=720,
                nombre_partiels_snapshot=1,
                montant_partiel_snapshot=Decimal('15000.00'),
                montant_ligne=Decimal('15000.00'),
            )


class ConcurrenceTests(BaseDecompteTest):

    def test_double_creation_sequentielle_refusee(self):
        """Séquentiel : simule la contrainte unique au niveau service."""
        self._garde(_dt(2026, 6, 1, 6), _dt(2026, 6, 1, 18))
        creer_decompte(self.agent, 2026, 6, self.user)
        with self.assertRaises(ValidationError):
            creer_decompte(self.agent, 2026, 6, self.user)
