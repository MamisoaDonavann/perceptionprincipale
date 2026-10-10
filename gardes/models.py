"""
Application gardes.

Contient :
- Garde : enregistrement d'une garde effectuée par un agent.

Règles métier :
- 1 partiel = 12 heures = 720 minutes.
- La durée est calculée à partir des dates/heures de début et de fin.
- Une durée non multiple de 720 minutes est signalée comme anomalie,
  sans arrondi automatique.
- Aucune suppression physique : l'annulation passe par un statut.
- Le tarif appliqué est conservé pour l'historique.
"""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, F


class Garde(models.Model):
    """
    Garde effectuée par un agent.

    Le calcul de la durée, du nombre de partiels et de la conformité
    est réalisé dans save() à partir des dates et heures.

    clean() valide la cohérence avec le tarif applicable.
    Il doit être appelé explicitement (formulaires, services).
    """

    STATUT_VALIDEE = 'VALIDEE'
    STATUT_ANNULEE = 'ANNULEE'

    STATUTS_CHOICES = [
        (STATUT_VALIDEE, 'Validée'),
        (STATUT_ANNULEE, 'Annulée'),
    ]

    DUREE_PARTIEL_MINUTES = 720

    agent = models.ForeignKey(
        'agents.Agent',
        on_delete=models.PROTECT,
        related_name='gardes',
        verbose_name="Agent"
    )
    mission = models.ForeignKey(
        'missions.Mission',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='gardes',
        verbose_name="Mission",
        help_text="Facultative."
    )
    tarif = models.ForeignKey(
        'tarifs.Tarif',
        on_delete=models.PROTECT,
        related_name='gardes',
        verbose_name="Tarif appliqué",
        help_text="Conserve l'historique du tarif utilisé."
    )
    date_heure_debut = models.DateTimeField(
        verbose_name="Date et heure de début"
    )
    date_heure_fin = models.DateTimeField(
        verbose_name="Date et heure de fin"
    )
    duree_minutes = models.PositiveIntegerField(
        verbose_name="Durée (minutes)",
        help_text="Calculée automatiquement. Non modifiable manuellement."
    )
    nombre_partiels = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Nombre de partiels",
        help_text="NULL si la durée n'est pas un multiple de 12 heures."
    )
    conforme = models.BooleanField(
        verbose_name="Conforme",
        help_text="Vrai si la durée est un multiple exact de 12 heures."
    )
    motif_anomalie = models.TextField(
        blank=True,
        default="",
        verbose_name="Motif d'anomalie",
        help_text="Obligatoire si la garde n'est pas conforme."
    )
    observation = models.TextField(
        null=True,
        blank=True,
        verbose_name="Observation"
    )
    statut = models.CharField(
        max_length=20,
        choices=STATUTS_CHOICES,
        default=STATUT_VALIDEE,
        verbose_name="Statut"
    )
    id_utilisateur_saisie = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='gardes_saisies',
        verbose_name="Saisie par"
    )
    date_saisie = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date de saisie"
    )
    date_maj = models.DateTimeField(
        auto_now=True,
        verbose_name="Dernière mise à jour"
    )

    class Meta:
        verbose_name = "Garde"
        verbose_name_plural = "Gardes"
        ordering = ['-date_heure_debut']
        constraints = [
            models.CheckConstraint(
                condition=Q(date_heure_fin__gt=F('date_heure_debut')),
                name='garde_date_fin_strictement_superieure_debut'
            ),
            models.CheckConstraint(
                condition=Q(duree_minutes__gt=0),
                name='garde_duree_minutes_strictement_positive'
            ),
            models.CheckConstraint(
                condition=Q(nombre_partiels__isnull=True) | Q(nombre_partiels__gt=0),
                name='garde_nombre_partiels_positif_ou_null'
            ),
            models.CheckConstraint(
                condition=Q(conforme=False) | Q(nombre_partiels__isnull=False),
                name='garde_conforme_implique_partiels'
            ),
            models.CheckConstraint(
                condition=Q(conforme=True) | ~Q(motif_anomalie=''),
                name='garde_non_conforme_implique_motif'
            ),
        ]
        indexes = [
            models.Index(fields=['agent', 'date_heure_debut']),
            models.Index(fields=['mission']),
            models.Index(fields=['tarif']),
            models.Index(fields=['statut']),
        ]

    def __str__(self):
        return f"Garde {self.agent.matricule} ({self.date_heure_debut:%Y-%m-%d %H:%M})"

    def _recalculer(self):
        """
        Recalcule durée, conformité et nombre de partiels
        à partir des dates et heures.
        """
        if not self.date_heure_debut or not self.date_heure_fin:
            return

        delta = self.date_heure_fin - self.date_heure_debut
        total_secondes = delta.total_seconds()

        if total_secondes <= 0:
            raise ValidationError(
                "La durée doit être strictement positive."
            )
        if total_secondes % 60 != 0:
            raise ValidationError(
                "La durée doit être un nombre entier de minutes. "
                "Corrigez les heures saisies."
            )

        self.duree_minutes = int(total_secondes // 60)

        if self.duree_minutes % self.DUREE_PARTIEL_MINUTES == 0:
            self.conforme = True
            self.nombre_partiels = self.duree_minutes // self.DUREE_PARTIEL_MINUTES
            self.motif_anomalie = ""
        else:
            self.conforme = False
            self.nombre_partiels = None
            if not self.motif_anomalie:
                self.motif_anomalie = "Durée non multiple de 12 heures"

    def save(self, *args, **kwargs):
        """
        Recalcule toujours les champs dérivés avant sauvegarde.
        Empêche l'écriture de valeurs incohérentes.
        """
        self._recalculer()
        super().save(*args, **kwargs)

    def clean(self):
        """
        Validation applicative.

        Vérifie que le tarif associé est bien applicable à la date
        de début de la garde.

        ATTENTION : clean() n'est pas appelé automatiquement par save().
        Il doit être appelé explicitement par les formulaires et
        le service creer_garde().
        """
        super().clean()

        if not self.tarif or not self.date_heure_debut:
            return

        date_garde = self.date_heure_debut.date()

        if not self.tarif.actif:
            raise ValidationError({
                'tarif': "Le tarif associé n'est pas actif."
            })
        if self.tarif.date_debut_validite > date_garde:
            raise ValidationError({
                'tarif': (
                    "Le tarif n'est pas encore en vigueur à la date "
                    "de la garde."
                )
            })
        if (
            self.tarif.date_fin_validite
            and self.tarif.date_fin_validite < date_garde
        ):
            raise ValidationError({
                'tarif': (
                    "Le tarif n'est plus en vigueur à la date "
                    "de la garde."
                )
            })
