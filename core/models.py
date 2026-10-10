"""
Application core.

Contient les modèles transverses :
- Unite : unité ou service d'affectation des agents.
- Parametre : configuration clé/valeur de l'application.
"""

from django.db import models
from django.conf import settings


class Unite(models.Model):
    """
    Représente une unité ou un service d'affectation.

    Aucune règle administrative officielle n'est présumée ici.
    La structure est volontairement simple et pourra évoluer.
    """

    code = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Code",
        help_text="Code unique de l'unité."
    )
    libelle = models.CharField(
        max_length=200,
        verbose_name="Libellé",
        help_text="Nom complet de l'unité."
    )
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name="Description",
        help_text="Description facultative."
    )
    actif = models.BooleanField(
        default=True,
        verbose_name="Actif",
        help_text="Désactiver une unité sans la supprimer."
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
        verbose_name = "Unité"
        verbose_name_plural = "Unités"
        ordering = ['code']

    def __str__(self):
        return f"{self.code} - {self.libelle}"


class Parametre(models.Model):
    """
    Configuration clé/valeur de l'application.

    Permet de stocker des paramètres sans modifier le schéma
    (exemple : fréquence de sauvegarde, format d'export).
    """

    cle = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Clé",
        help_text="Clé unique du paramètre."
    )
    valeur = models.TextField(
        verbose_name="Valeur",
        help_text="Valeur du paramètre."
    )
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name="Description",
        help_text="Description facultative."
    )
    date_maj = models.DateTimeField(
        auto_now=True,
        verbose_name="Date de mise à jour"
    )
    id_utilisateur_maj = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Modifié par",
        help_text="Utilisateur ayant effectué la dernière modification."
    )

    class Meta:
        verbose_name = "Paramètre"
        verbose_name_plural = "Paramètres"
        ordering = ['cle']

    def __str__(self):
        return self.cle
