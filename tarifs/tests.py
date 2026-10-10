from datetime import date

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase

from .models import Tarif

User = get_user_model()


class TarifModelTests(TestCase):
    """Tests techniques minimaux. Aucune donnée administrative réelle."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='test_tarif_user',
            password='test_password_2026'
        )

    def test_montant_positif_accepte(self):
        t = Tarif.objects.create(
            montant_partiel='15000.00',
            date_debut_validite=date(2026, 1, 1),
            id_utilisateur_createur=self.user,
        )
        self.assertEqual(t.montant_partiel, 15000)

    def test_montant_zero_refuse(self):
        with self.assertRaises(IntegrityError):
            Tarif.objects.create(
                montant_partiel='0.00',
                date_debut_validite=date(2026, 1, 1),
                id_utilisateur_createur=self.user,
            )

    def test_montant_negatif_refuse(self):
        with self.assertRaises(IntegrityError):
            Tarif.objects.create(
                montant_partiel='-100.00',
                date_debut_validite=date(2026, 1, 1),
                id_utilisateur_createur=self.user,
            )

    def test_date_fin_null_acceptee(self):
        t = Tarif.objects.create(
            montant_partiel='15000.00',
            date_debut_validite=date(2026, 1, 1),
            date_fin_validite=None,
            id_utilisateur_createur=self.user,
        )
        self.assertIsNone(t.date_fin_validite)

    def test_date_fin_egale_debut_acceptee(self):
        t = Tarif.objects.create(
            montant_partiel='15000.00',
            date_debut_validite=date(2026, 1, 1),
            date_fin_validite=date(2026, 1, 1),
            id_utilisateur_createur=self.user,
        )
        self.assertEqual(t.date_fin_validite, date(2026, 1, 1))

    def test_date_fin_anterieure_refusee(self):
        with self.assertRaises(IntegrityError):
            Tarif.objects.create(
                montant_partiel='15000.00',
                date_debut_validite=date(2026, 6, 1),
                date_fin_validite=date(2026, 1, 1),
                id_utilisateur_createur=self.user,
            )

    def test_utilisateur_protege_contre_suppression(self):
        Tarif.objects.create(
            montant_partiel='15000.00',
            date_debut_validite=date(2026, 1, 1),
            id_utilisateur_createur=self.user,
        )
        with self.assertRaises(Exception):
            self.user.delete()
