"""
Application audit.

Contient :
- JournalAudit : journal des actions sensibles.

Les entrées du journal sont immuables : ni modification, ni suppression
physique ne sont autorisées après création.
"""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class JournalAudit(models.Model):
    """
    Entrée du journal d'audit.

    Chaque entrée enregistre une action sensible (création, modification,
    annulation, validation) sur une entité métier.

    Les entrées sont immuables une fois créées.
    """

    ACTION_CREATION = 'CREATION'
    ACTION_MODIFICATION = 'MODIFICATION'
    ACTION_ANNULATION = 'ANNULATION'
    ACTION_VALIDATION = 'VALIDATION'

    ACTIONS_CHOICES = [
        (ACTION_CREATION, 'Création'),
        (ACTION_MODIFICATION, 'Modification'),
        (ACTION_ANNULATION, 'Annulation'),
        (ACTION_VALIDATION, 'Validation'),
    ]

    id_utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='journal_audit',
        verbose_name="Utilisateur",
        help_text="Utilisateur ayant effectué l'action."
    )
    action = models.CharField(
        max_length=20,
        choices=ACTIONS_CHOICES,
        verbose_name="Action"
    )
    entite_concernee = models.CharField(
        max_length=100,
        verbose_name="Entité concernée",
        help_text="Exemple : 'gardes.Garde'."
    )
    id_entite_concernee = models.BigIntegerField(
        verbose_name="Identifiant de l'entité",
        help_text="Identifiant de l'objet concerné."
    )
    date_action = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date de l'action"
    )
    valeurs_avant = models.JSONField(
        null=True,
        blank=True,
        verbose_name="Valeurs avant modification"
    )
    valeurs_apres = models.JSONField(
        null=True,
        blank=True,
        verbose_name="Valeurs après modification"
    )
    commentaire = models.TextField(
        blank=True,
        default="",
        verbose_name="Commentaire"
    )
    adresse_ip = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name="Adresse IP"
    )

    class Meta:
        verbose_name = "Entrée d'audit"
        verbose_name_plural = "Journal d'audit"
        ordering = ['-date_action']
        indexes = [
            models.Index(fields=['entite_concernee', 'id_entite_concernee']),
            models.Index(fields=['id_utilisateur', '-date_action']),
        ]

    def __str__(self):
        return f"[{self.date_action:%Y-%m-%d %H:%M}] {self.action} {self.entite_concernee}#{self.id_entite_concernee}"

    def save(self, *args, **kwargs):
        """
        Refuse toute modification d'une entrée existante.

        Une entrée d'audit ne peut être que créée, jamais modifiée.
        """
        if not self._state.adding:
            raise ValidationError(
                "Une entrée d'audit ne peut pas être modifiée."
            )
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """
        Refuse toute suppression physique d'une entrée d'audit.
        """
        raise ValidationError(
            "Une entrée d'audit ne peut pas être supprimée."
        )
