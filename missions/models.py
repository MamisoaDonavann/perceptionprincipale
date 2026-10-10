"""
Application missions.

Contient :
- Mission : opération ou intervention officielle.
- ParticipationMission : participation individuelle d'un agent à une mission.

Les statuts proposés sont PROVISOIRES et à valider avec la Perception
Principale avant l'implémentation définitive.
"""

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, F

from agents.models import Agent


class Mission(models.Model):
    """
    Mission ou intervention officielle.

    Notes :
    - Le numéro officiel est FACULTATIF pour la V1.
      Il sera obligatoire lorsque la règle administrative sera confirmée.
    - Plusieurs missions sans numéro officiel peuvent coexister
      (normalisation de '' en None dans save()).
    - Les statuts proposés sont PROVISOIRES et à valider.
    - La date de fin ne peut pas être antérieure à la date de début.
    """

    # --- Statuts PROVISOIRES (à valider) ---
    STATUT_PLANIFIEE = 'PLANIFIEE'
    STATUT_EN_COURS = 'EN_COURS'
    STATUT_TERMINEE = 'TERMINEE'
    STATUT_ANNULEE = 'ANNULEE'

    STATUTS_CHOICES = [
        (STATUT_PLANIFIEE, 'Planifiée'),
        (STATUT_EN_COURS, 'En cours'),
        (STATUT_TERMINEE, 'Terminée'),
        (STATUT_ANNULEE, 'Annulée'),
    ]

    numero_officiel = models.CharField(
        max_length=100,
        unique=True,
        null=True,
        blank=True,
        verbose_name="Numéro officiel",
        help_text="Facultatif en V1. Unique lorsqu'il est renseigné."
    )
    libelle = models.CharField(
        max_length=200,
        verbose_name="Libellé"
    )
    description = models.TextField(
        null=True,
        blank=True,
        verbose_name="Description"
    )
    lieu = models.CharField(
        max_length=200,
        null=True,
        blank=True,
        verbose_name="Lieu"
    )
    date_debut = models.DateTimeField(
        verbose_name="Date et heure de début"
    )
    date_fin = models.DateTimeField(
        verbose_name="Date et heure de fin"
    )
    statut = models.CharField(
        max_length=20,
        choices=STATUTS_CHOICES,
        default=STATUT_PLANIFIEE,
        verbose_name="Statut",
        help_text="PROVISOIRE : valeurs à valider avec la Perception Principale."
    )
    observation = models.TextField(
        null=True,
        blank=True,
        verbose_name="Observation"
    )
    date_creation = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date de création"
    )
    date_maj = models.DateTimeField(
        auto_now=True,
        verbose_name="Date de mise à jour"
    )

    class Meta:
        verbose_name = "Mission"
        verbose_name_plural = "Missions"
        ordering = ['-date_debut']
        constraints = [
            models.CheckConstraint(
                condition=Q(date_fin__gte=F('date_debut')),
                name='mission_date_fin_superieure_ou_egale_debut'
            ),
        ]

    def __str__(self):
        if self.numero_officiel:
            return f"{self.numero_officiel} - {self.libelle}"
        return self.libelle

    def save(self, *args, **kwargs):
        """
        Normalise les chaînes vides en None pour numero_officiel.

        Objectif : permettre plusieurs missions sans numéro officiel
        sans conflit d'unicité PostgreSQL (qui n'autorise qu'un seul '').
        """
        if self.numero_officiel == '':
            self.numero_officiel = None
        super().save(*args, **kwargs)


class ParticipationMission(models.Model):
    """
    Participation individuelle d'un agent à une mission.

    Notes :
    - Un même agent ne peut participer qu'une seule fois à une mission
      (UniqueConstraint sur mission + agent).
    - Les clés étrangères utilisent on_delete=PROTECT pour préserver
      l'historique : ni la mission ni l'agent ne peuvent être supprimés
      physiquement tant qu'une participation existe.
    - Les dates de participation sont obligatoires.
    - La méthode clean() vérifie que la période de participation est
      comprise dans la période de la mission.

    ATTENTION :
    clean() n'est PAS appelé automatiquement par save().
    Il doit être appelé explicitement par les formulaires (ModelForm)
    ou par les services métier.
    """

    mission = models.ForeignKey(
        Mission,
        on_delete=models.PROTECT,
        related_name='participations',
        verbose_name="Mission"
    )
    agent = models.ForeignKey(
        Agent,
        on_delete=models.PROTECT,
        related_name='participations_missions',
        verbose_name="Agent"
    )
    date_debut_participation = models.DateTimeField(
        verbose_name="Début de participation"
    )
    date_fin_participation = models.DateTimeField(
        verbose_name="Fin de participation"
    )
    observation = models.TextField(
        null=True,
        blank=True,
        verbose_name="Observation"
    )
    date_creation = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date de création"
    )

    class Meta:
        verbose_name = "Participation à une mission"
        verbose_name_plural = "Participations aux missions"
        ordering = ['mission', 'agent']
        constraints = [
            models.UniqueConstraint(
                fields=['mission', 'agent'],
                name='participation_mission_agent_unique'
            ),
            models.CheckConstraint(
                condition=Q(date_fin_participation__gte=F('date_debut_participation')),
                name='participation_date_fin_superieure_ou_egale_debut'
            ),
        ]
        indexes = [
            models.Index(fields=['mission', 'agent']),
            models.Index(fields=['agent', 'date_debut_participation']),
        ]

    def __str__(self):
        return f"{self.agent.matricule} - {self.mission}"

    def clean(self):
        """
        Validation applicative : la participation doit être comprise
        dans la période de la mission.

        Rappel : clean() doit être appelé explicitement.
        """
        super().clean()

        if not self.mission_id:
            return
        if not self.date_debut_participation or not self.date_fin_participation:
            return

        if self.date_debut_participation < self.mission.date_debut:
            raise ValidationError({
                'date_debut_participation': (
                    "La date de début de participation ne peut pas être "
                    "antérieure à la date de début de la mission."
                )
            })
        if self.date_fin_participation > self.mission.date_fin:
            raise ValidationError({
                'date_fin_participation': (
                    "La date de fin de participation ne peut pas être "
                    "postérieure à la date de fin de la mission."
                )
            })
