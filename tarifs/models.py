"""
Application tarifs.

Contient :
- Tarif : montant applicable à un partiel de garde de 12 heures,
  pour une période de validité donnée.

Règles métier :
- Le montant est strictement positif.
- La période de validité est définie par date_debut_validite et
  date_fin_validite (cette dernière facultative).
- Aucune contrainte d'exclusion temporelle en V1 : la règle sur les
  chevauchements reste à valider avec la Perception Principale.
- Un tarif erroné n'est pas supprimé : il est désactivé via « actif ».
"""

from django.conf import settings
from django.db import models
from django.db.models import Q, F


class Tarif(models.Model):
    """
    Tarif applicable à un partiel de garde de 12 heures.

    Notes :
    - Le montant est en ariary (Ar).
    - La validité est déterminée par les dates et le champ « actif ».
    - Un tarif n'est applicable à une date que si :
        * il est actif ;
        * la date est >= date_debut_validite ;
        * date_fin_validite est NULL ou >= cette date.
    - Le champ « actif » permet de désactiver un tarif erroné sans
      altérer son historique de validité.
    - Aucune suppression physique : on conserve les tarifs historiques.
    """

    montant_partiel = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Montant d'un partiel (Ar)",
        help_text="Montant en ariary pour un partiel de 12 heures. Strictement positif."
    )
    date_debut_validite = models.DateField(
        verbose_name="Début de validité"
    )
    date_fin_validite = models.DateField(
        null=True,
        blank=True,
        verbose_name="Fin de validité",
        help_text="Vide signifie que la fin de validité n'est pas définie."
    )
    actif = models.BooleanField(
        default=True,
        verbose_name="Actif",
        help_text="Désactivation logique sans suppression."
    )
    id_utilisateur_createur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='tarifs_crees',
        verbose_name="Créé par",
        help_text="Utilisateur ayant créé ce tarif. Protégé contre la suppression."
    )
    date_creation = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date de création"
    )
    motif_modification = models.TextField(
        blank=True,
        default="",
        verbose_name="Motif de modification",
        help_text="Facultatif. Justifie un changement de tarif."
    )

    class Meta:
        verbose_name = "Tarif"
        verbose_name_plural = "Tarifs"
        ordering = ['-date_debut_validite']
        constraints = [
            models.CheckConstraint(
                condition=Q(montant_partiel__gt=0),
                name='tarif_montant_partiel_strictement_positif'
            ),
            models.CheckConstraint(
                condition=(
                    Q(date_fin_validite__isnull=True)
                    | Q(date_fin_validite__gte=F('date_debut_validite'))
                ),
                name='tarif_date_fin_superieure_ou_egale_debut'
            ),
        ]
        indexes = [
            models.Index(fields=['date_debut_validite', 'date_fin_validite']),
            models.Index(fields=['actif']),
        ]

    def __str__(self):
        fin = self.date_fin_validite.isoformat() if self.date_fin_validite else "en cours"
        return f"{self.montant_partiel} Ar / partiel ({self.date_debut_validite} - {fin})"
