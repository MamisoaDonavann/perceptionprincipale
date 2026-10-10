"""
Application paiements.

Contient :
- CompteurOP             : compteur annuel pour la numérotation OP.
- OrdrePaiement          : en-tête administratif du paiement.
- PeriodePaiement        : ligne liée à un décompte validé.
- Paiement               : versement effectif (partiel ou complet).
- ConfirmationReception  : preuve de réception par un agent.

Règles :
- Aucune suppression physique. PROTECT partout. Audit systématique.
- Decimal(14,2) pour tous les montants. Jamais de float.
- Decimal strict repris des décomptes validés.
"""

from django.conf import settings
from django.db import models
from django.db.models import Q, F


class CompteurOP(models.Model):
    """Compteur annuel pour la génération des numéros OP-AAAA-NNNN."""

    annee = models.PositiveIntegerField(unique=True, verbose_name="Année")
    dernier_numero = models.PositiveIntegerField(
        default=0, verbose_name="Dernier numéro attribué"
    )

    class Meta:
        verbose_name = "Compteur OP"
        verbose_name_plural = "Compteurs OP"
        constraints = [
            models.CheckConstraint(
                condition=Q(dernier_numero__gte=0),
                name='compteurop_dernier_numero_positif'
            ),
        ]

    def __str__(self):
        return f"Compteur {self.annee} : {self.dernier_numero}"


class OrdrePaiement(models.Model):
    """
    Ordre de paiement (OP).

    Un OP concerne un seul agent bénéficiaire et peut regrouper
    plusieurs décomptes mensuels validés.
    """

    STATUT_BROUILLON = 'BROUILLON'
    STATUT_VALIDE = 'VALIDE'
    STATUT_PAYE = 'PAYE'
    STATUT_ANNULE = 'ANNULE'

    STATUTS_CHOICES = [
        (STATUT_BROUILLON, 'Brouillon'),
        (STATUT_VALIDE, 'Validé'),
        (STATUT_PAYE, 'Payé'),
        (STATUT_ANNULE, 'Annulé'),
    ]

    numero_op = models.CharField(
        max_length=20, unique=True, verbose_name="Numéro OP"
    )
    agent_beneficiaire = models.ForeignKey(
        'agents.Agent',
        on_delete=models.PROTECT,
        related_name='ordres_paiement',
        verbose_name="Agent bénéficiaire"
    )
    annee = models.PositiveIntegerField(verbose_name="Année")
    statut = models.CharField(
        max_length=20, choices=STATUTS_CHOICES,
        default=STATUT_BROUILLON, verbose_name="Statut"
    )
    montant_total = models.DecimalField(
        max_digits=14, decimal_places=2,
        verbose_name="Montant total (Ar)"
    )
    montant_net_paye = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        verbose_name="Montant net payé (Ar)",
        help_text="Cache recalculé systématiquement dans les services."
    )
    id_utilisateur_createur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='op_crees', verbose_name="Créé par"
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name="Date de création"
    )
    id_utilisateur_validateur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        null=True, blank=True, related_name='op_valides',
        verbose_name="Validé par"
    )
    date_validation = models.DateTimeField(
        null=True, blank=True, verbose_name="Date de validation"
    )
    cloture_administrative = models.BooleanField(
        default=False, verbose_name="Clôture administrative"
    )
    date_cloture = models.DateTimeField(
        null=True, blank=True, verbose_name="Date de clôture"
    )
    id_utilisateur_cloture = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        null=True, blank=True, related_name='op_clotures',
        verbose_name="Clôturé par"
    )
    motif_annulation = models.TextField(
        blank=True, default="", verbose_name="Motif d'annulation"
    )
    observation = models.TextField(
        blank=True, default="", verbose_name="Observation"
    )

    class Meta:
        verbose_name = "Ordre de paiement"
        verbose_name_plural = "Ordres de paiement"
        ordering = ['-annee', '-numero_op']
        permissions = [
            ('creer_ordre_paiement', 'Peut créer un ordre de paiement'),
            ('valider_ordre_paiement', 'Peut valider un ordre de paiement'),
            ('annuler_ordre_paiement', 'Peut annuler un ordre de paiement'),
            ('enregistrer_paiement', 'Peut enregistrer un paiement'),
            ('annuler_paiement', 'Peut annuler un paiement'),
            ('confirmer_reception', 'Peut confirmer une réception'),
            ('annuler_confirmation', 'Peut annuler une confirmation'),
            ('consulter_ordre_paiement', 'Peut consulter un ordre de paiement'),
            ('cloturer_ordre_paiement', 'Peut clôturer administrativement un ordre'),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(montant_net_paye__gte=0),
                name='ordrepaiement_net_positif'
            ),
            models.CheckConstraint(
                condition=Q(montant_net_paye__lte=F('montant_total')),
                name='ordrepaiement_net_inferieur_ou_egal_total'
            ),
            # C1 : validateur requis uniquement pour VALIDE ou PAYE
            models.CheckConstraint(
                condition=(
                    ~Q(statut__in=['VALIDE', 'PAYE'])
                    | (Q(id_utilisateur_validateur__isnull=False)
                       & Q(date_validation__isnull=False))
                ),
                name='ordrepaiement_validateur_requis_pour_valide_paye'
            ),
            # Clôture cohérente
            models.CheckConstraint(
                condition=(
                    Q(cloture_administrative=False)
                    | (Q(date_cloture__isnull=False)
                       & Q(id_utilisateur_cloture__isnull=False))
                ),
                name='ordrepaiement_cloture_coherente'
            ),
            # Motif obligatoire si ANNULE
            models.CheckConstraint(
                condition=(
                    ~Q(statut='ANNULE') | ~Q(motif_annulation='')
                ),
                name='ordrepaiement_motif_requis_si_annule'
            ),
        ]

    def __str__(self):
        return f"{self.numero_op} ({self.statut})"


class PeriodePaiement(models.Model):
    """
    Ligne d'un OP liée à un décompte validé.
    """

    ordre_paiement = models.ForeignKey(
        OrdrePaiement, on_delete=models.PROTECT,
        related_name='periodes', verbose_name="Ordre de paiement"
    )
    decompte = models.ForeignKey(
        'decomptes.Decompte', on_delete=models.PROTECT,
        related_name='periodes_paiement', verbose_name="Décompte"
    )
    montant_source = models.DecimalField(
        max_digits=14, decimal_places=2,
        verbose_name="Montant source (Ar)",
        help_text="Copie figée du montant du décompte validé."
    )
    reservation_active = models.BooleanField(
        default=True, verbose_name="Réservation active",
        help_text="Passe à False lorsque le décompte est libéré."
    )
    date_ajout = models.DateTimeField(
        auto_now_add=True, verbose_name="Date d'ajout"
    )

    class Meta:
        verbose_name = "Période de paiement"
        verbose_name_plural = "Périodes de paiement"
        ordering = ['ordre_paiement', 'decompte']
        constraints = [
            models.UniqueConstraint(
                fields=['decompte'],
                condition=Q(reservation_active=True),
                name='periode_paiement_decompte_actif_unique'
            ),
            models.UniqueConstraint(
                fields=['ordre_paiement', 'decompte'],
                name='periode_paiement_op_decompte_unique'
            ),
        ]

    def __str__(self):
        return f"{self.ordre_paiement.numero_op} ← {self.decompte}"


class Paiement(models.Model):
    """Versement effectif (partiel ou complet)."""

    MODE_ESPECES = 'ESPECES'
    MODE_CHEQUE = 'CHEQUE'
    MODE_VIREMENT = 'VIREMENT'
    MODE_AUTRE = 'AUTRE'
    MODES_CHOICES = [
        (MODE_ESPECES, 'Espèces'),
        (MODE_CHEQUE, 'Chèque'),
        (MODE_VIREMENT, 'Virement'),
        (MODE_AUTRE, 'Autre'),
    ]

    STATUT_ENREGISTRE = 'ENREGISTRE'
    STATUT_ANNULE = 'ANNULE'
    STATUTS_CHOICES = [
        (STATUT_ENREGISTRE, 'Enregistré'),
        (STATUT_ANNULE, 'Annulé'),
    ]

    ordre_paiement = models.ForeignKey(
        OrdrePaiement, on_delete=models.PROTECT,
        related_name='paiements', verbose_name="Ordre de paiement"
    )
    montant = models.DecimalField(
        max_digits=14, decimal_places=2, verbose_name="Montant (Ar)"
    )
    date_paiement = models.DateTimeField(verbose_name="Date du paiement")
    mode_paiement = models.CharField(
        max_length=20, choices=MODES_CHOICES, verbose_name="Mode de paiement"
    )
    reference = models.CharField(
        max_length=100, blank=True, default="", verbose_name="Référence"
    )
    statut = models.CharField(
        max_length=20, choices=STATUTS_CHOICES,
        default=STATUT_ENREGISTRE, verbose_name="Statut"
    )
    motif_annulation = models.TextField(
        blank=True, default="", verbose_name="Motif d'annulation"
    )
    id_utilisateur_enregistreur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='paiements_enregistres', verbose_name="Enregistré par"
    )
    date_enregistrement = models.DateTimeField(
        auto_now_add=True, verbose_name="Date d'enregistrement"
    )
    id_utilisateur_annulateur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        null=True, blank=True, related_name='paiements_annules',
        verbose_name="Annulé par"
    )
    date_annulation = models.DateTimeField(
        null=True, blank=True, verbose_name="Date d'annulation"
    )

    class Meta:
        verbose_name = "Paiement"
        verbose_name_plural = "Paiements"
        ordering = ['-date_paiement']
        constraints = [
            models.CheckConstraint(
                condition=Q(montant__gt=0),
                name='paiement_montant_positif'
            ),
            models.CheckConstraint(
                condition=(
                    Q(statut='ENREGISTRE')
                    | (Q(motif_annulation__gt='')
                       & Q(id_utilisateur_annulateur__isnull=False)
                       & Q(date_annulation__isnull=False))
                ),
                name='paiement_annule_coherent'
            ),
        ]

    def __str__(self):
        return f"Paiement #{self.pk} {self.montant} Ar ({self.statut})"


class ConfirmationReception(models.Model):
    """Preuve de réception par un agent (justificatif signé)."""

    MODE_PAPIER_NUMERISE = 'PAPIER_NUMERISE'
    MODE_ELECTRONIQUE = 'ELECTRONIQUE'
    MODES_CHOICES = [
        (MODE_PAPIER_NUMERISE, 'Papier numérisé'),
        (MODE_ELECTRONIQUE, 'Électronique'),
    ]

    STATUT_CONFIRME = 'CONFIRME'
    STATUT_ANNULE = 'ANNULE'
    STATUTS_CHOICES = [
        (STATUT_CONFIRME, 'Confirmé'),
        (STATUT_ANNULE, 'Annulé'),
    ]

    paiement = models.ForeignKey(
        Paiement, on_delete=models.PROTECT,
        related_name='confirmations', verbose_name="Paiement"
    )
    date_confirmation = models.DateTimeField(verbose_name="Date de confirmation")
    id_utilisateur_confirmation = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='confirmations_effectuees', verbose_name="Confirmé par"
    )
    mode = models.CharField(
        max_length=20, choices=MODES_CHOICES, verbose_name="Mode"
    )
    justificatif = models.FileField(
        upload_to='confirmations/%Y/%m/',
        verbose_name="Justificatif signé"
    )
    statut = models.CharField(
        max_length=20, choices=STATUTS_CHOICES,
        default=STATUT_CONFIRME, verbose_name="Statut"
    )
    motif_annulation = models.TextField(
        blank=True, default="", verbose_name="Motif d'annulation"
    )
    id_utilisateur_annulateur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        null=True, blank=True, related_name='confirmations_annulees',
        verbose_name="Annulé par"
    )
    date_annulation = models.DateTimeField(
        null=True, blank=True, verbose_name="Date d'annulation"
    )

    class Meta:
        verbose_name = "Confirmation de réception"
        verbose_name_plural = "Confirmations de réception"
        ordering = ['-date_confirmation']
        constraints = [
            models.UniqueConstraint(
                fields=['paiement'],
                condition=Q(statut='CONFIRME'),
                name='confirmation_paiement_active_unique'
            ),
            models.CheckConstraint(
                condition=(
                    Q(statut='CONFIRME')
                    | (Q(motif_annulation__gt='')
                       & Q(id_utilisateur_annulateur__isnull=False)
                       & Q(date_annulation__isnull=False))
                ),
                name='confirmation_annulee_coherente'
            ),
        ]

    def __str__(self):
        return f"Confirmation #{self.pk} du paiement #{self.paiement_id}"
