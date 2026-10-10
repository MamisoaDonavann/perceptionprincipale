"""
Application decomptes.

Contient :
- Decompte : décompte mensuel du montant dû à un agent.
- LigneDecompte : ligne figée d'un décompte.

Règles métier :
- Un décompte couvre un mois civil complet (annee, mois).
- Un seul décompte par (agent, annee, mois).
- Les gardes sont affectées au mois de leur date_heure_debut.
- Les montants sont figés à la création (snapshots).
- Aucune suppression physique : PROTECT sur les références historiques.
"""

from django.conf import settings
from django.db import models
from django.db.models import Q


class Decompte(models.Model):
    """
    Décompte mensuel du montant dû à un agent.

    Statuts :
    - BROUILLON : créé et calculé, en attente de vérification.
    - VALIDE : vérifié et approuvé. Non modifiable directement.
    """

    STATUT_BROUILLON = 'BROUILLON'
    STATUT_VALIDE = 'VALIDE'

    STATUTS_CHOICES = [
        (STATUT_BROUILLON, 'Brouillon'),
        (STATUT_VALIDE, 'Validé'),
    ]

    agent = models.ForeignKey(
        'agents.Agent',
        on_delete=models.PROTECT,
        related_name='decomptes',
        verbose_name="Agent"
    )
    annee = models.PositiveIntegerField(verbose_name="Année")
    mois = models.PositiveSmallIntegerField(verbose_name="Mois")
    statut = models.CharField(
        max_length=20,
        choices=STATUTS_CHOICES,
        default=STATUT_BROUILLON,
        verbose_name="Statut"
    )
    montant_total = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        verbose_name="Montant total (Ar)",
        help_text="Figé à la création. Non recalculé dynamiquement."
    )
    nombre_gardes_retunes = models.PositiveIntegerField(
        default=0,
        verbose_name="Nombre de gardes retenues"
    )
    nombre_gardes_non_conformes_exclues = models.PositiveIntegerField(
        default=0,
        verbose_name="Gardes non conformes exclues",
        help_text="Signalement : gardes présentes sur la période mais exclues."
    )
    id_utilisateur_createur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='decomptes_crees',
        verbose_name="Créé par"
    )
    date_creation = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date de création"
    )
    id_utilisateur_validateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='decomptes_valides',
        verbose_name="Validé par"
    )
    date_validation = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Date de validation"
    )

    class Meta:
        verbose_name = "Décompte"
        verbose_name_plural = "Décomptes"
        ordering = ['-annee', '-mois', 'agent']
        constraints = [
            models.UniqueConstraint(
                fields=['agent', 'annee', 'mois'],
                name='decompte_agent_annee_mois_unique'
            ),
            models.CheckConstraint(
                condition=Q(annee__gte=1900) & Q(annee__lte=2200),
                name='decompte_annee_valide'
            ),
            models.CheckConstraint(
                condition=Q(mois__gte=1) & Q(mois__lte=12),
                name='decompte_mois_valide'
            ),
            models.CheckConstraint(
                condition=(
                    Q(statut='BROUILLON')
                    | (
                        Q(id_utilisateur_validateur__isnull=False)
                        & Q(date_validation__isnull=False)
                    )
                ),
                name='decompte_valide_avec_validateur'
            ),
        ]

    def __str__(self):
        return (
            f"Décompte {self.agent.matricule} "
            f"{self.annee}/{self.mois:02d} ({self.statut})"
        )


class LigneDecompte(models.Model):
    """
    Ligne figée d'un décompte : instantané d'une garde au moment du calcul.

    Conserve les valeurs effectives (durée, partiels, tarif, montants)
    indépendamment de toute modification ultérieure des objets sources.
    """

    decompte = models.ForeignKey(
        Decompte,
        on_delete=models.PROTECT,
        related_name='lignes',
        verbose_name="Décompte"
    )
    garde = models.ForeignKey(
        'gardes.Garde',
        on_delete=models.PROTECT,
        related_name='lignes_decompte',
        verbose_name="Garde source"
    )
    tarif = models.ForeignKey(
        'tarifs.Tarif',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='lignes_decompte',
        verbose_name="Tarif historique"
    )
    duree_minutes_snapshot = models.PositiveIntegerField(
        verbose_name="Durée (min) — figée"
    )
    nombre_partiels_snapshot = models.PositiveIntegerField(
        verbose_name="Nombre de partiels — figé"
    )
    montant_partiel_snapshot = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Montant d'un partiel (Ar) — figé"
    )
    montant_ligne = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        verbose_name="Montant de la ligne (Ar) — figé"
    )

    class Meta:
        verbose_name = "Ligne de décompte"
        verbose_name_plural = "Lignes de décompte"
        ordering = ['decompte', 'garde__date_heure_debut']
        constraints = [
            # Une garde ne peut apparaître que dans un seul décompte.
            # Protection contre la double utilisation, y compris en concurrence.
            models.UniqueConstraint(
                fields=['garde'],
                name='ligne_decompte_garde_globale_unique'
            ),
            models.CheckConstraint(
                condition=Q(nombre_partiels_snapshot__gt=0),
                name='ligne_decompte_partiels_positif'
            ),
            models.CheckConstraint(
                condition=Q(montant_partiel_snapshot__gt=0),
                name='ligne_decompte_montant_partiel_positif'
            ),
            models.CheckConstraint(
                condition=Q(montant_ligne__gt=0),
                name='ligne_decompte_montant_positif'
            ),
        ]

    def __str__(self):
        return f"Ligne garde={self.garde_id} montant={self.montant_ligne} Ar"
