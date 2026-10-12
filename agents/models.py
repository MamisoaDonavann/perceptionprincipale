"""
Application agents.

Contient :
- Agent : identité administrative d'un agent des forces de l'ordre.
- AffectationAgent : historique des affectations d'un agent à une unité.

Règles et statuts marqués « PROVISOIRE » doivent être validés
auprès de la Perception Principale avant l'implémentation définitive.
"""

from django.db import models
from django.db.models import Q, F

from core.models import Unite


class Agent(models.Model):
    """
    Agent des forces de l'ordre, bénéficiaire potentiel des paiements.

    Notes :
    - Le matricule est obligatoire et unique.
      Le format administratif officiel reste à confirmer.
    - Le CIN est facultatif et unique lorsqu'il est renseigné.
    - Le grade est un texte libre : aucune liste officielle n'est codée en dur.
    - Les statuts d'agent sont PROVISOIRES et doivent être validés.
    - Le champ « actif » est distinct du statut administratif.
      Leur interaction n'est pas définie pour la V1.
    - Aucune suppression physique n'est prévue : on désactive via « actif ».
    """

    # --- Statuts provisoires (à valider) ---
    STATUT_ACTIF = 'ACTIF'
    STATUT_SUSPENDU = 'SUSPENDU'
    STATUT_RADIE = 'RADIE'

    STATUTS_CHOICES = [
        (STATUT_ACTIF, 'Actif'),
        (STATUT_SUSPENDU, 'Suspendu'),
        (STATUT_RADIE, 'Radié'),
    ]

    # --- Choix de sexe (facultatif, à valider) ---
    SEXE_M = 'M'
    SEXE_F = 'F'

    SEXE_CHOICES = [
        (SEXE_M, 'Masculin'),
        (SEXE_F, 'Féminin'),
    ]

    # --- Identification administrative ---
    matricule = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Matricule",
        help_text="Matricule administratif unique. Format à valider."
    )
    nom = models.CharField(
        max_length=150,
        verbose_name="Nom"
    )
    prenoms = models.CharField(
        max_length=200,
        verbose_name="Prénoms"
    )
    cin = models.CharField(
        max_length=50,
        unique=True,
        null=True,
        blank=True,
        verbose_name="CIN",
        help_text="Carte d'identité nationale. Facultatif et unique si renseigné."
    )

    # --- Informations personnelles (facultatives) ---
    date_naissance = models.DateField(
        null=True,
        blank=True,
        verbose_name="Date de naissance"
    )
    lieu_naissance = models.CharField(
        max_length=200,
        null=True,
        blank=True,
        verbose_name="Lieu de naissance"
    )
    sexe = models.CharField(
        max_length=1,
        choices=SEXE_CHOICES,
        null=True,
        blank=True,
        verbose_name="Sexe"
    )
    telephone = models.CharField(
        max_length=30,
        null=True,
        blank=True,
        verbose_name="Téléphone",
        help_text="Facultatif. Aucune unicité imposée en V1."
    )

    adresse = models.CharField(
        max_length=200,
        blank=True,
        default="",
        verbose_name="Adresse",
        help_text="Adresse administrative du titulaire. Facultatif."
    )

    # --- Fonction ---
    grade = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Grade ou fonction",
        help_text="Texte libre. Aucune liste officielle codée en dur."
    )

    # --- Statut administratif (PROVISOIRE) ---
    statut_agent = models.CharField(
        max_length=20,
        choices=STATUTS_CHOICES,
        default=STATUT_ACTIF,
        verbose_name="Statut administratif",
        help_text="PROVISOIRE : valeurs à valider avec la Perception Principale."
    )

    # --- Activation logique ---
    actif = models.BooleanField(
        default=True,
        verbose_name="Actif",
        help_text="Désactivation logique. Aucune suppression physique."
    )

    observation = models.TextField(
        null=True,
        blank=True,
        verbose_name="Observation"
    )

    # --- Traçabilité ---
    date_creation = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date de création"
    )
    date_maj = models.DateTimeField(
        auto_now=True,
        verbose_name="Date de mise à jour"
    )

    class Meta:
        verbose_name = "Agent"
        verbose_name_plural = "Agents"
        ordering = ['nom', 'prenoms']

    def __str__(self):
        return f"{self.matricule} - {self.nom} {self.prenoms}"


class AffectationAgent(models.Model):
    """
    Historique des affectations d'un agent à une unité.

    Notes :
    - Plusieurs affectations sont possibles pour un même agent.
    - Aucune contrainte d'unicité (agent, unité) n'est imposée :
      un agent peut revenir dans une même unité plusieurs fois.
    - Aucune contrainte d'exclusion temporelle n'est imposée en V1 :
      la règle sur les chevauchements et les affectations simultanées
      reste à valider avec la Perception Principale.
    - date_fin = NULL signifie « affectation en cours ».
    - Contrainte simple : date_fin NULL ou >= date_debut.
    """

    agent = models.ForeignKey(
        Agent,
        on_delete=models.PROTECT,
        related_name='affectations',
        verbose_name="Agent"
    )
    unite = models.ForeignKey(
        Unite,
        on_delete=models.PROTECT,
        related_name='affectations_agents',
        verbose_name="Unité"
    )
    date_debut = models.DateField(
        verbose_name="Date de début"
    )
    date_fin = models.DateField(
        null=True,
        blank=True,
        verbose_name="Date de fin",
        help_text="Vide signifie que l'affectation est en cours."
    )
    motif = models.TextField(
        null=True,
        blank=True,
        verbose_name="Motif",
        help_text="Motif facultatif du changement d'affectation."
    )
    date_creation = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date de création"
    )

    class Meta:
        verbose_name = "Affectation d'agent"
        verbose_name_plural = "Affectations d'agents"
        ordering = ['agent', '-date_debut']
        constraints = [
            models.CheckConstraint(
                condition=Q(date_fin__isnull=True) | Q(date_fin__gte=F('date_debut')),
                name='affectation_date_fin_superieure_ou_egale_debut'
            ),
        ]
        indexes = [
            models.Index(fields=['agent', 'date_debut']),
            models.Index(fields=['unite', 'date_debut']),
        ]

    def __str__(self):
        fin = self.date_fin if self.date_fin else "en cours"
        return f"{self.agent.matricule} → {self.unite.code} ({self.date_debut} - {fin})"
