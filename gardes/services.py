"""
Services de l'application gardes.

Fonctions principales :
- creer_garde() : point d'entrée applicatif pour créer une garde.
- annuler_garde() : annulation contrôlée et auditée.
"""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q

from audit.models import JournalAudit
from audit.services import journaliser
from tarifs.models import Tarif

from .models import Garde


def _trouver_tarif_applicable(date_garde):
    """
    Retourne le tarif unique applicable à la date donnée.

    Lève ValidationError si aucun tarif ou si plusieurs tarifs
    sont applicables.
    """
    tarifs = Tarif.objects.filter(
        actif=True,
        date_debut_validite__lte=date_garde,
    ).filter(
        Q(date_fin_validite__isnull=True)
        | Q(date_fin_validite__gte=date_garde)
    )

    count = tarifs.count()
    if count == 0:
        raise ValidationError(
            "Aucun tarif applicable à cette date. "
            "Vérifiez les périodes de validité des tarifs."
        )
    if count > 1:
        raise ValidationError(
            f"Plusieurs tarifs ({count}) sont applicables à cette date. "
            "Corrigez les périodes de validité avant de créer la garde."
        )
    return tarifs.get()


def _detecter_chevauchements(agent, date_heure_debut, date_heure_fin, exclude_pk=None):
    """
    Retourne la liste des gardes VALIDEE de l'agent qui chevauchent
    la période donnée.
    """
    qs = Garde.objects.filter(
        agent=agent,
        statut=Garde.STATUT_VALIDEE,
        date_heure_debut__lt=date_heure_fin,
        date_heure_fin__gt=date_heure_debut,
    )
    if exclude_pk is not None:
        qs = qs.exclude(pk=exclude_pk)
    return list(qs)


@transaction.atomic
def creer_garde(
    user,
    agent,
    date_heure_debut,
    date_heure_fin,
    tarif=None,
    mission=None,
    observation=None,
):
    """
    Point d'entrée applicatif pour créer une garde.

    Paramètres :
    - user : utilisateur Django effectuant la création (obligatoire).
    - agent : instance Agent (obligatoire).
    - date_heure_debut : datetime aware (obligatoire).
    - date_heure_fin : datetime aware (obligatoire).
    - tarif : instance Tarif (optionnel). Si None, sélectionné
      automatiquement selon la date de début.
    - mission : instance Mission (optionnel).
    - observation : texte libre (optionnel).

    Retourne un tuple (garde, avertissements) où avertissements est
    une liste de chaînes signalant des chevauchements éventuels.

    Lève ValidationError si les règles métier ne sont pas respectées.

    L'écriture de la garde et de l'entrée d'audit se fait dans une
    même transaction : si l'audit échoue, la création est annulée.
    """
    if user is None:
        raise ValidationError("Utilisateur obligatoire.")

    date_garde = date_heure_debut.date()

    if tarif is None:
        tarif = _trouver_tarif_applicable(date_garde)

    garde = Garde(
        agent=agent,
        mission=mission,
        tarif=tarif,
        date_heure_debut=date_heure_debut,
        date_heure_fin=date_heure_fin,
        observation=observation,
        statut=Garde.STATUT_VALIDEE,
        id_utilisateur_saisie=user,
    )

    # Calculer les champs dérivés AVANT full_clean, sinon les
    # contraintes de durée / conformité échouent sur des valeurs
    # par défaut incohérentes.
    garde._recalculer()

    garde.full_clean(exclude=None, validate_unique=False)
    garde.save()

    avertissements = []
    chevauchements = _detecter_chevauchements(
        agent=agent,
        date_heure_debut=date_heure_debut,
        date_heure_fin=date_heure_fin,
        exclude_pk=garde.pk,
    )
    if chevauchements:
        avertissements.append(
            f"{len(chevauchements)} garde(s) chevauchante(s) détectée(s) "
            f"pour cet agent sur la période."
        )

    journaliser(
        user=user,
        action=JournalAudit.ACTION_CREATION,
        entite='gardes.Garde',
        id_entite=garde.pk,
        apres={
            'agent_id': garde.agent_id,
            'mission_id': garde.mission_id,
            'tarif_id': garde.tarif_id,
            'date_heure_debut': garde.date_heure_debut.isoformat(),
            'date_heure_fin': garde.date_heure_fin.isoformat(),
            'duree_minutes': garde.duree_minutes,
            'nombre_partiels': garde.nombre_partiels,
            'conforme': garde.conforme,
            'statut': garde.statut,
        },
        commentaire='Création de garde',
    )

    return garde, avertissements


@transaction.atomic
def annuler_garde(user, garde, motif):
    """
    Annule une garde (passage au statut ANNULEE).

    Ne supprime jamais physiquement la garde.
    Journalise l'action.

    Lève ValidationError si :
    - la garde est déjà annulée ;
    - le motif est vide.
    """
    if user is None:
        raise ValidationError("Utilisateur obligatoire.")
    if garde.statut == Garde.STATUT_ANNULEE:
        raise ValidationError("Cette garde est déjà annulée.")
    if not motif or not motif.strip():
        raise ValidationError("Un motif d'annulation est obligatoire.")

    ancien_statut = garde.statut
    garde.statut = Garde.STATUT_ANNULEE
    garde.save(update_fields=['statut', 'date_maj'])

    journaliser(
        user=user,
        action=JournalAudit.ACTION_ANNULATION,
        entite='gardes.Garde',
        id_entite=garde.pk,
        avant={'statut': ancien_statut},
        apres={'statut': garde.statut},
        commentaire=motif,
    )

    return garde
