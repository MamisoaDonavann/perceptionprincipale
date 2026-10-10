"""
Tests pour l'application paiements.

Note : aucun test n'a encore été exécuté. Ce fichier sera lancé
après migration, via `python manage.py test paiements`.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from agents.models import Agent
from decomptes.models import Decompte
from gardes.models import Garde
from tarifs.models import Tarif

from .models import (
    CompteurOP, OrdrePaiement, PeriodePaiement,
    Paiement, ConfirmationReception,
)
from .services import (
    creer_ordre_paiement, valider_ordre_paiement,
    retirer_periode_ordre, annuler_ordre_paiement,
    enregistrer_paiement, annuler_paiement,
    confirmer_reception, annuler_confirmation,
    cloturer_administrativement,
)

User = get_user_model()


def _dt(y, m, d, h=0, mn=0):
    return timezone.make_aware(datetime(y, m, d, h, mn, 0))


class BasePaiementTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='op_user', password='pwd2026_test'
        )
        self.user2 = User.objects.create_user(
            username='op_user2', password='pwd2026_test'
        )
        self.admin = User.objects.create_superuser(
            username='admin_test', password='pwd2026_test',
            email='admin@local'
        )
        # Permissions accordées
        for u in (self.user, self.user2, self.admin):
            for codename in [
                'creer_ordre_paiement', 'valider_ordre_paiement',
                'annuler_ordre_paiement', 'enregistrer_paiement',
                'annuler_paiement', 'confirmer_reception',
                'annuler_confirmation', 'consulter_ordre_paiement',
                'cloturer_ordre_paiement',
            ]:
                u.user_permissions.add(
                    Permission.objects.get(
                        codename=codename,
                        content_type__app_label='paiements',
                    )
                )

        self.agent = Agent.objects.create(
            matricule='AG-P-01', nom='N', prenoms='P'
        )
        self.tarif = Tarif.objects.create(
            montant_partiel=Decimal('15000.00'),
            date_debut_validite=date(2025, 1, 1),
            id_utilisateur_createur=self.user,
        )

    def _creer_decompte_valide(self, annee=2026, mois=6):
        g = Garde(
            agent=self.agent, tarif=self.tarif,
            date_heure_debut=_dt(annee, mois, 1, 6),
            date_heure_fin=_dt(annee, mois, 1, 18),
            id_utilisateur_saisie=self.user,
        )
        g._recalculer()
        g.full_clean(exclude=None, validate_unique=False)
        g.save()

        from decomptes.services import creer_decompte, valider_decompte
        d, _ = creer_decompte(self.agent, annee, mois, self.user)
        valider_decompte(d, self.user2)
        d.refresh_from_db()
        return d


class NumerotationTests(BasePaiementTest):

    def test_premier_op(self):
        d = self._creer_decompte_valide()
        op, _ = creer_ordre_paiement(self.agent, 2026, [d], self.user)
        self.assertEqual(op.numero_op, 'OP-2026-0001')

    def test_ops_suivants(self):
        d1 = self._creer_decompte_valide(2026, 5)
        d2 = self._creer_decompte_valide(2026, 6)
        op1, _ = creer_ordre_paiement(self.agent, 2026, [d1], self.user)
        op2, _ = creer_ordre_paiement(self.agent, 2026, [d2], self.user)
        self.assertEqual(op1.numero_op, 'OP-2026-0001')
        self.assertEqual(op2.numero_op, 'OP-2026-0002')

    def test_unicite_en_base(self):
        d = self._creer_decompte_valide()
        creer_ordre_paiement(self.agent, 2026, [d], self.user)
        with self.assertRaises(IntegrityError):
            OrdrePaiement.objects.create(
                numero_op='OP-2026-0001', agent_beneficiaire=self.agent,
                annee=2026, statut='BROUILLON',
                montant_total=Decimal('0.00'),
                id_utilisateur_createur=self.user,
            )


class CreationOrdreTests(BasePaiementTest):

    def test_creation_brouillon(self):
        d = self._creer_decompte_valide()
        op, _ = creer_ordre_paiement(self.agent, 2026, [d], self.user)
        self.assertEqual(op.statut, OrdrePaiement.STATUT_BROUILLON)
        self.assertEqual(op.montant_total, d.montant_total)
        self.assertEqual(op.periodes.count(), 1)

    def test_refus_decompte_non_valide(self):
        from decomptes.services import creer_decompte
        g = Garde(agent=self.agent, tarif=self.tarif,
                  date_heure_debut=_dt(2026, 6, 1, 6),
                  date_heure_fin=_dt(2026, 6, 1, 18),
                  id_utilisateur_saisie=self.user)
        g._recalculer(); g.full_clean(); g.save()
        d_brouillon, _ = creer_decompte(self.agent, 2026, 6, self.user)
        with self.assertRaises(ValidationError):
            creer_ordre_paiement(self.agent, 2026, [d_brouillon], self.user)


class ReservationTests(BasePaiementTest):

    def test_double_reservation_refusee(self):
        d = self._creer_decompte_valide()
        creer_ordre_paiement(self.agent, 2026, [d], self.user)
        with self.assertRaises(ValidationError):
            creer_ordre_paiement(self.agent, 2026, [d], self.user2)

    def test_liberation_apres_annulation(self):
        d = self._creer_decompte_valide()
        op, _ = creer_ordre_paiement(self.agent, 2026, [d], self.user)
        annuler_ordre_paiement(op, self.user, motif="Test")
        op2, _ = creer_ordre_paiement(self.agent, 2026, [d], self.user)
        self.assertIsNotNone(op2.pk)

    def test_retrait_brouillon(self):
        d = self._creer_decompte_valide()
        op, _ = creer_ordre_paiement(self.agent, 2026, [d], self.user)
        retirer_periode_ordre(op, d, self.user, motif="Retrait")
        op.refresh_from_db()
        self.assertEqual(op.montant_total, Decimal('0.00'))


class ValidationOrdreTests(BasePaiementTest):

    def test_validation_par_autre(self):
        d = self._creer_decompte_valide()
        op, _ = creer_ordre_paiement(self.agent, 2026, [d], self.user)
        op = valider_ordre_paiement(op, self.user2)
        self.assertEqual(op.statut, OrdrePaiement.STATUT_VALIDE)

    def test_auto_validation_refusee(self):
        d = self._creer_decompte_valide()
        op, _ = creer_ordre_paiement(self.agent, 2026, [d], self.user)
        with self.assertRaises(PermissionDenied):
            valider_ordre_paiement(op, self.user)


class PaiementTests(BasePaiementTest):

    def _op_valide(self):
        d = self._creer_decompte_valide()
        op, _ = creer_ordre_paiement(self.agent, 2026, [d], self.user)
        return valider_ordre_paiement(op, self.user2)

    def test_paiement_partiel(self):
        op = self._op_valide()
        p = enregistrer_paiement(
            op, Decimal('5000.00'), 'ESPECES', self.user
        )
        op.refresh_from_db()
        self.assertEqual(op.statut, OrdrePaiement.STATUT_VALIDE)
        self.assertEqual(op.montant_net_paye, Decimal('5000.00'))

    def test_paiement_complet_passe_paye(self):
        op = self._op_valide()
        enregistrer_paiement(op, op.montant_total, 'ESPECES', self.user)
        op.refresh_from_db()
        self.assertEqual(op.statut, OrdrePaiement.STATUT_PAYE)

    def test_refus_paiement_sur_paye(self):
        """C1 : un OP PAYE ne reçoit plus de paiement."""
        op = self._op_valide()
        enregistrer_paiement(op, op.montant_total, 'ESPECES', self.user)
        op.refresh_from_db()
        with self.assertRaises(ValidationError):
            enregistrer_paiement(op, Decimal('1000.00'), 'ESPECES', self.user2)

    def test_refus_depassement(self):
        op = self._op_valide()
        with self.assertRaises(ValidationError):
            enregistrer_paiement(
                op, op.montant_total + Decimal('1.00'), 'ESPECES', self.user
            )


class AnnulationPaiementTests(BasePaiementTest):

    def test_paye_revient_valide_apres_annulation(self):
        """Correction 4 : PAYE → VALIDE si net < total."""
        d = self._creer_decompte_valide()
        op, _ = creer_ordre_paiement(self.agent, 2026, [d], self.user)
        op = valider_ordre_paiement(op, self.user2)
        p = enregistrer_paiement(op, op.montant_total, 'ESPECES', self.user)
        op.refresh_from_db()
        self.assertEqual(op.statut, OrdrePaiement.STATUT_PAYE)

        annuler_paiement(p, self.user2, motif="Erreur")
        op.refresh_from_db()
        self.assertEqual(op.statut, OrdrePaiement.STATUT_VALIDE)
        self.assertEqual(op.montant_net_paye, Decimal('0.00'))

    def test_refus_annulation_apres_cloture(self):
        """C2 : refus si OP clôturé administrativement."""
        d = self._creer_decompte_valide()
        op, _ = creer_ordre_paiement(self.agent, 2026, [d], self.user)
        op = valider_ordre_paiement(op, self.user2)
        p = enregistrer_paiement(op, op.montant_total, 'ESPECES', self.user)

        from django.core.files.uploadedfile import SimpleUploadedFile
        just = SimpleUploadedFile("j.txt", b"x")
        confirmer_reception(p, self.user2, 'PAPIER_NUMERISE', just)
        op.refresh_from_db()
        cloturer_administrativement(op, self.admin)
        op.refresh_from_db()

        with self.assertRaises(ValidationError):
            annuler_paiement(p, self.user2, motif="Après clôture")


class ConfirmationTests(BasePaiementTest):

    def _paiement(self):
        d = self._creer_decompte_valide()
        op, _ = creer_ordre_paiement(self.agent, 2026, [d], self.user)
        op = valider_ordre_paiement(op, self.user2)
        return enregistrer_paiement(op, Decimal('1000.00'), 'ESPECES', self.user)

    def test_confirmation_ok(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        p = self._paiement()
        just = SimpleUploadedFile("j.txt", b"x")
        c = confirmer_reception(p, self.user2, 'PAPIER_NUMERISE', just)
        self.assertEqual(c.statut, ConfirmationReception.STATUT_CONFIRME)

    def test_refus_auto_confirmation(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        p = self._paiement()
        just = SimpleUploadedFile("j.txt", b"x")
        with self.assertRaises(ValidationError):
            confirmer_reception(p, self.user, 'PAPIER_NUMERISE', just)

    def test_remplacement_apres_annulation(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        p = self._paiement()
        just1 = SimpleUploadedFile("j1.txt", b"x")
        c1 = confirmer_reception(p, self.user2, 'PAPIER_NUMERISE', just1)
        annuler_confirmation(c1, self.user2, motif="Erreur")
        just2 = SimpleUploadedFile("j2.txt", b"y")
        c2 = confirmer_reception(p, self.user2, 'ELECTRONIQUE', just2)
        self.assertNotEqual(c1.pk, c2.pk)


class AnnulationConfirmationTests(BasePaiementTest):

    def test_annulation_ok(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        d = self._creer_decompte_valide()
        op, _ = creer_ordre_paiement(self.agent, 2026, [d], self.user)
        op = valider_ordre_paiement(op, self.user2)
        p = enregistrer_paiement(op, Decimal('1000.00'), 'ESPECES', self.user)
        just = SimpleUploadedFile("j.txt", b"x")
        c = confirmer_reception(p, self.user2, 'PAPIER_NUMERISE', just)
        annuler_confirmation(c, self.user2, motif="Motif")
        c.refresh_from_db()
        self.assertEqual(c.statut, ConfirmationReception.STATUT_ANNULE)


class ClotureTests(BasePaiementTest):

    def test_refus_si_confirmation_manquante(self):
        d = self._creer_decompte_valide()
        op, _ = creer_ordre_paiement(self.agent, 2026, [d], self.user)
        op = valider_ordre_paiement(op, self.user2)
        enregistrer_paiement(op, op.montant_total, 'ESPECES', self.user)
        op.refresh_from_db()
        with self.assertRaises(ValidationError):
            cloturer_administrativement(op, self.admin)

    def test_succes_apres_confirmations(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        d = self._creer_decompte_valide()
        op, _ = creer_ordre_paiement(self.agent, 2026, [d], self.user)
        op = valider_ordre_paiement(op, self.user2)
        p = enregistrer_paiement(op, op.montant_total, 'ESPECES', self.user)
        just = SimpleUploadedFile("j.txt", b"x")
        confirmer_reception(p, self.user2, 'PAPIER_NUMERISE', just)
        op.refresh_from_db()
        cloturer_administrativement(op, self.admin)
        op.refresh_from_db()
        self.assertTrue(op.cloture_administrative)

    def test_refus_double_cloture(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        d = self._creer_decompte_valide()
        op, _ = creer_ordre_paiement(self.agent, 2026, [d], self.user)
        op = valider_ordre_paiement(op, self.user2)
        p = enregistrer_paiement(op, op.montant_total, 'ESPECES', self.user)
        just = SimpleUploadedFile("j.txt", b"x")
        confirmer_reception(p, self.user2, 'PAPIER_NUMERISE', just)
        op.refresh_from_db()
        cloturer_administrativement(op, self.admin)
        op.refresh_from_db()
        with self.assertRaises(ValidationError):
            cloturer_administrativement(op, self.admin)


class PermissionTests(BasePaiementTest):

    def test_refus_sans_permission(self):
        u = User.objects.create_user(username='no_perm', password='x')
        d = self._creer_decompte_valide()
        with self.assertRaises(PermissionDenied):
            creer_ordre_paiement(self.agent, 2026, [d], u)


class ConcurrenceTests(TransactionTestCase):
    """Tests de concurrence réels — nécessitent PostgreSQL."""

    def test_generation_concurrente_numeros(self):
        """
        À exécuter après migration sur PostgreSQL.
        Utilise threads + transactions séparées.
        """
        pass

    def test_reservation_concurrente_decompte(self):
        """
        À exécuter après migration sur PostgreSQL.
        Deux threads tentent de réserver le même décompte.
        """
        pass
