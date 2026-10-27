"""
Services de l'application decomptes.

Fonctions principales :
- creer_decompte(agent, annee, mois, user)
- valider_decompte(decompte, user)

Les opérations d'écriture et d'audit sont atomiques.
"""

from datetime import datetime
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from audit.models import JournalAudit
from audit.services import journaliser
from gardes.models import Garde

from .models import Decompte, LigneDecompte


def _periode_mensuelle(annee, mois):
    """
    Retourne (debut, fin) en datetime aware dans le fuseau courant.
    debut inclus, fin exclue.
    """
    tz = timezone.get_current_timezone()
    debut = timezone.make_aware(datetime(annee, mois, 1, 0, 0, 0), timezone=tz)
    if mois == 12:
        fin = timezone.make_aware(
            datetime(annee + 1, 1, 1, 0, 0, 0), timezone=tz
        )
    else:
        fin = timezone.make_aware(
            datetime(annee, mois + 1, 1, 0, 0, 0), timezone=tz
        )
    return debut, fin


@transaction.atomic
def creer_decompte(agent, annee, mois, user):
    """
    Crée un décompte mensuel pour un agent.

    Étapes :
    1. Valider entrées (annee, mois, user).
    2. Vérifier absence de décompte existant.
    3. Sélectionner les gardes éligibles (VALIDEE, conforme, mois de début).
    4. Compter les gardes non conformes exclues.
    5. Vérifier qu'aucune garde n'est déjà utilisée dans un autre décompte.
    6. Créer le décompte et ses lignes figées.
    7. Journaliser (dans la même transaction).

    Retourne (decompte, avertissements).
    """
    if user is None:
        raise ValidationError("Utilisateur obligatoire.")
    if not isinstance(annee, int) or annee < 1900 or annee > 2200:
        raise ValidationError("Année invalide (1900-2200).")
    if not isinstance(mois, int) or mois < 1 or mois > 12:
        raise ValidationError("Mois invalide (1-12).")

    if Decompte.objects.filter(agent=agent, annee=annee, mois=mois).exists():
        raise ValidationError(
            f"Un décompte existe déjà pour {agent.matricule} "
            f"({annee}/{mois:02d})."
        )

    debut, fin = _periode_mensuelle(annee, mois)

    gardes_conformes = list(
        Garde.objects.filter(
            agent=agent,
            statut=Garde.STATUT_VALIDEE,
            conforme=True,
            date_heure_debut__gte=debut,
            date_heure_debut__lt=fin,
        )
        .select_related('tarif')
        .order_by('date_heure_debut')
    )

    nb_non_conformes = Garde.objects.filter(
        agent=agent,
        statut=Garde.STATUT_VALIDEE,
        conforme=False,
        date_heure_debut__gte=debut,
        date_heure_debut__lt=fin,
    ).count()

    # 👇 CORRECTION ICI : On refuse la création si aucune garde conforme
    if not gardes_conformes:
        raise ValidationError(
            f"Aucune garde conforme éligible pour l'agent {agent.matricule} "
            f"sur le mois {mois:02d}/{annee}. Le décompte n'a pas été créé."
        )

    # Vérification préventive : gardes déjà utilisées dans un autre décompte.
    ids = [g.pk for g in gardes_conformes]
    deja_utilisees = list(
        LigneDecompte.objects
        .filter(garde_id__in=ids)
        .values_list('garde_id', flat=True)
    )
    if deja_utilisees:
        raise ValidationError(
            f"{len(deja_utilisees)} garde(s) déjà utilisée(s) dans "
            f"un autre décompte. Vérifiez les décomptes existants."
        )

    decompte = Decompte(
        agent=agent,
        annee=annee,
        mois=mois,
        statut=Decompte.STATUT_BROUILLON,
        montant_total=Decimal('0.00'),
        nombre_gardes_retunes=0,
        nombre_gardes_non_conformes_exclues=nb_non_conformes,
        id_utilisateur_createur=user,
    )

    avertissements = []
    if nb_non_conformes > 0:
        avertissements.append(
            f"{nb_non_conformes} garde(s) non conforme(s) exclue(s) "
            f"du calcul. À examiner séparément."
        )

    try:
        decompte.save()
    except IntegrityError:
        raise ValidationError(
            f"Un décompte existe déjà pour {agent.matricule} "
            f"({annee}/{mois:02d})."
        )

    total = Decimal('0.00')

    try:
        for g in gardes_conformes:
            if g.tarif is None:
                raise ValidationError(
                    f"La garde #{g.pk} n'a pas de tarif associé."
                )
            montant_partiel = g.tarif.montant_partiel
            montant_ligne = montant_partiel * g.nombre_partiels
            LigneDecompte.objects.create(
                decompte=decompte,
                garde=g,
                tarif=g.tarif,
                duree_minutes_snapshot=g.duree_minutes,
                nombre_partiels_snapshot=g.nombre_partiels,
                montant_partiel_snapshot=montant_partiel,
                montant_ligne=montant_ligne,
            )
            total += montant_ligne
    except IntegrityError:
        raise ValidationError(
            "Une ou plusieurs gardes ont été utilisées simultanément "
            "dans un autre décompte. Aucun décompte n'a été créé."
        )

    decompte.montant_total = total
    decompte.nombre_gardes_retunes = len(gardes_conformes)
    decompte.save(update_fields=['montant_total', 'nombre_gardes_retunes'])

    journaliser(
        user=user,
        action=JournalAudit.ACTION_CREATION,
        entite='decomptes.Decompte',
        id_entite=decompte.pk,
        apres={
            'agent_id': agent.pk,
            'annee': annee,
            'mois': mois,
            'montant_total': str(total),
            'nombre_gardes_retunes': len(gardes_conformes),
            'nombre_gardes_non_conformes_exclues': nb_non_conformes,
            'statut': decompte.statut,
        },
        commentaire='Création de décompte',
    )

    return decompte, avertissements


@transaction.atomic
def valider_decompte(decompte, user):
    """
    Valide un décompte BROUILLON.

    Vérifie que le décompte est bien en BROUILLON, enregistre le
    validateur et la date, puis journalise dans la même transaction.
    """
    if user is None:
        raise ValidationError("Utilisateur obligatoire.")
    if decompte.statut != Decompte.STATUT_BROUILLON:
        raise ValidationError(
            f"Seul un décompte BROUILLON peut être validé. "
            f"Statut actuel : {decompte.statut}."
        )

    decompte.statut = Decompte.STATUT_VALIDE
    decompte.id_utilisateur_validateur = user
    decompte.date_validation = timezone.now()
    decompte.save(update_fields=[
        'statut', 'id_utilisateur_validateur', 'date_validation',
    ])

    journaliser(
        user=user,
        action=JournalAudit.ACTION_VALIDATION,
        entite='decomptes.Decompte',
        id_entite=decompte.pk,
        avant={'statut': Decompte.STATUT_BROUILLON},
        apres={'statut': Decompte.STATUT_VALIDE},
        commentaire='Validation de décompte',
    )

    return decompte
