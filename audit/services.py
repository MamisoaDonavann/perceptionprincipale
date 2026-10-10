"""
Services de l'application audit.

Fonction principale :
- journaliser() : enregistre une action sensible dans le journal d'audit.
"""

from django.core.exceptions import ValidationError

from .models import JournalAudit


def journaliser(
    user,
    action,
    entite,
    id_entite,
    avant=None,
    apres=None,
    commentaire="",
    adresse_ip=None,
):
    """
    Enregistre une entrée d'audit.

    Paramètres :
    - user : utilisateur Django ayant effectué l'action.
    - action : valeur parmi JournalAudit.ACTIONS_CHOICES.
    - entite : chaîne identifiant l'entité (ex. 'gardes.Garde').
    - id_entite : identifiant de l'objet concerné.
    - avant : dict JSON des valeurs avant modification (optionnel).
    - apres : dict JSON des valeurs après modification (optionnel).
    - commentaire : texte libre (optionnel).
    - adresse_ip : chaîne IP (optionnel).

    Retourne l'instance JournalAudit créée.

    En cas d'erreur, lève une exception : l'appelant doit pouvoir
    annuler sa transaction pour préserver la cohérence.

    ATTENTION :
    Cette fonction ne doit jamais recevoir de mots de passe
    ni de secrets dans les champs avant/apres.
    """
    actions_valides = dict(JournalAudit.ACTIONS_CHOICES)
    if action not in actions_valides:
        raise ValidationError(f"Action d'audit inconnue : {action}")

    return JournalAudit.objects.create(
        id_utilisateur=user,
        action=action,
        entite_concernee=entite,
        id_entite_concernee=id_entite,
        valeurs_avant=avant,
        valeurs_apres=apres,
        commentaire=commentaire or "",
        adresse_ip=adresse_ip,
    )
