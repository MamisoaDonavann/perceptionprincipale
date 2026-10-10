"""
Services de l'application paiements.

Toutes les opérations financières sont atomiques et auditées via
audit.services.journaliser.
"""

from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.utils import timezone

from audit.models import JournalAudit
from audit.services import journaliser
from agents.models import Agent
from decomptes.models import Decompte

from .models import (
    CompteurOP, OrdrePaiement, PeriodePaiement,
    Paiement, ConfirmationReception,
)


# ---------------------------------------------------------------------
# Numérotation
# ---------------------------------------------------------------------

def _next_numero_op(annee):
    """
    Génère un N° OP-AAAA-NNNN unique pour l'année.
    Doit être appelé DANS une transaction active.

    La tentative d'INSERT initial est protégée par un savepoint
    pour ne pas invalider la transaction externe en cas de
    IntegrityError.
    """
    try:
        with transaction.atomic():
            CompteurOP.objects.create(annee=annee, dernier_numero=1)
        return f"OP-{annee}-0001"
    except IntegrityError:
        pass

    compteur = (
        CompteurOP.objects
        .select_for_update()
        .get(annee=annee)
    )
    compteur.dernier_numero += 1
    compteur.save(update_fields=['dernier_numero'])
    return f"OP-{annee}-{compteur.dernier_numero:04d}"


# ---------------------------------------------------------------------
# Ordre de paiement
# ---------------------------------------------------------------------

@transaction.atomic
def creer_ordre_paiement(agent, annee, decomptes, user, observation=""):
    """
    Crée un OP BROUILLON avec réservation active des décomptes.

    Sécurités :
    - Décomptes VALIDE et du même agent.
    - Verrouillage des Decompte existants pour sérialiser
      les réservations concurrentes.
    - Capture de IntegrityError résiduel.
    """
    if not user.has_perm('paiements.creer_ordre_paiement'):
        raise PermissionDenied("Permission requise : paiements.creer_ordre_paiement.")

    if not decomptes:
        raise ValidationError("Au moins un décompte est requis.")

    decomptes = list(decomptes)
    ids = [d.pk for d in decomptes]

    # Vérifie que tous les décomptes sont VALIDE et du même agent
    for d in decomptes:
        if d.statut != Decompte.STATUT_VALIDE:
            raise ValidationError(
                f"Le décompte #{d.pk} n'est pas VALIDE."
            )
        if d.agent_id != agent.pk:
            raise ValidationError(
                f"Le décompte #{d.pk} n'appartient pas à l'agent."
            )

    # Verrouillage des lignes Decompte (les lignes existent) → sérialise
    # les créations concurrentes.
    list(
        Decompte.objects
        .select_for_update()
        .filter(pk__in=ids)
    )

    # Après lock : vérifier qu'aucune réservation active n'existe déjà
    if PeriodePaiement.objects.filter(
        decompte_id__in=ids, reservation_active=True
    ).exists():
        raise ValidationError(
            "Un ou plusieurs décomptes sont déjà réservés par un autre OP."
        )

    numero = _next_numero_op(annee)
    montant_total = sum((d.montant_total for d in decomptes), Decimal('0.00'))

    ordre = OrdrePaiement.objects.create(
        numero_op=numero,
        agent_beneficiaire=agent,
        annee=annee,
        statut=OrdrePaiement.STATUT_BROUILLON,
        montant_total=montant_total,
        montant_net_paye=Decimal('0.00'),
        id_utilisateur_createur=user,
        observation=observation,
    )

    try:
        for d in decomptes:
            PeriodePaiement.objects.create(
                ordre_paiement=ordre,
                decompte=d,
                montant_source=d.montant_total,
                reservation_active=True,
            )
    except IntegrityError:
        raise ValidationError(
            "Réservation concurrente détectée : un décompte a été réservé "
            "simultanément par un autre ordre."
        )

    journaliser(
        user=user,
        action=JournalAudit.ACTION_CREATION,
        entite='paiements.OrdrePaiement',
        id_entite=ordre.pk,
        apres={
            'numero_op': ordre.numero_op,
            'agent_id': agent.pk,
            'annee': annee,
            'montant_total': str(ordre.montant_total),
            'statut': ordre.statut,
        },
        commentaire='Création OP',
    )
    return ordre, []


@transaction.atomic
def valider_ordre_paiement(ordre, user):
    """BROUILLON → VALIDE par un user ≠ créateur."""
    if not user.has_perm('paiements.valider_ordre_paiement'):
        raise PermissionDenied("Permission requise : paiements.valider_ordre_paiement.")
    if user.pk == ordre.id_utilisateur_createur_id:
        raise PermissionDenied("Le créateur ne peut pas valider son propre ordre.")

    ordre = OrdrePaiement.objects.select_for_update().get(pk=ordre.pk)
    if ordre.statut != OrdrePaiement.STATUT_BROUILLON:
        raise ValidationError("Seul un OP BROUILLON peut être validé.")
    if not ordre.periodes.filter(reservation_active=True).exists():
        raise ValidationError("L'OP doit contenir au moins une période active.")

    ordre.statut = OrdrePaiement.STATUT_VALIDE
    ordre.id_utilisateur_validateur = user
    ordre.date_validation = timezone.now()
    ordre.save(update_fields=['statut', 'id_utilisateur_validateur', 'date_validation'])

    journaliser(
        user=user,
        action=JournalAudit.ACTION_VALIDATION,
        entite='paiements.OrdrePaiement',
        id_entite=ordre.pk,
        avant={'statut': 'BROUILLON'},
        apres={'statut': 'VALIDE'},
        commentaire='Validation OP',
    )
    return ordre


@transaction.atomic
def retirer_periode_ordre(ordre, decompte, user, motif):
    """Retire une période d'un OP BROUILLON."""
    if not user.has_perm('paiements.creer_ordre_paiement'):
        raise PermissionDenied("Permission requise.")

    ordre = OrdrePaiement.objects.select_for_update().get(pk=ordre.pk)
    if ordre.statut != OrdrePaiement.STATUT_BROUILLON:
        raise ValidationError("Seul un OP BROUILLON peut être modifié.")
    if not motif or not motif.strip():
        raise ValidationError("Motif obligatoire.")

    periode = PeriodePaiement.objects.filter(
        ordre_paiement=ordre, decompte=decompte, reservation_active=True
    ).first()
    if not periode:
        raise ValidationError("Période introuvable ou déjà libérée.")

    periode.reservation_active = False
    periode.save(update_fields=['reservation_active'])

    nouveau_total = sum(
        (p.montant_source for p in ordre.periodes.filter(reservation_active=True)),
        Decimal('0.00')
    )
    ordre.montant_total = nouveau_total
    ordre.save(update_fields=['montant_total'])

    journaliser(
        user=user, action=JournalAudit.ACTION_MODIFICATION,
        entite='paiements.OrdrePaiement', id_entite=ordre.pk,
        avant={'montant_total': str(periode.montant_source)},
        apres={'montant_total': str(nouveau_total)},
        commentaire=f'Retrait période : {motif}',
    )
    return ordre


@transaction.atomic
def annuler_ordre_paiement(ordre, user, motif):
    """Annule un OP. Refus si paiements actifs. Libère les réservations."""
    if not user.has_perm('paiements.annuler_ordre_paiement'):
        raise PermissionDenied("Permission requise.")
    if not motif or not motif.strip():
        raise ValidationError("Motif obligatoire.")

    ordre = OrdrePaiement.objects.select_for_update().get(pk=ordre.pk)
    if ordre.statut == OrdrePaiement.STATUT_ANNULE:
        raise ValidationError("OP déjà annulé.")
    if ordre.paiements.filter(statut=Paiement.STATUT_ENREGISTRE).exists():
        raise ValidationError(
            "Des paiements actifs existent. Régularisez-les d'abord."
        )

    ancien = ordre.statut
    ordre.statut = OrdrePaiement.STATUT_ANNULE
    ordre.motif_annulation = motif
    ordre.save(update_fields=['statut', 'motif_annulation'])

    ordre.periodes.filter(reservation_active=True).update(reservation_active=False)

    journaliser(
        user=user, action=JournalAudit.ACTION_ANNULATION,
        entite='paiements.OrdrePaiement', id_entite=ordre.pk,
        avant={'statut': ancien}, apres={'statut': 'ANNULE'},
        commentaire=motif,
    )
    return ordre


# ---------------------------------------------------------------------
# Paiements
# ---------------------------------------------------------------------

def _recalcul_net(ordre):
    """Recalcule le net depuis les paiements ENREGISTRE (Decimal)."""
    result = ordre.paiements.filter(
        statut=Paiement.STATUT_ENREGISTRE
    ).aggregate(s=Sum('montant'))
    return result['s'] or Decimal('0.00')


@transaction.atomic
def enregistrer_paiement(ordre, montant, mode, user,
                         date_paiement=None, reference=""):
    """
    Enregistre un paiement. C1 : statut doit être VALIDE.
    Verrouille l'OP, recalcule le net, refuse si dépassement.
    """
    if not user.has_perm('paiements.enregistrer_paiement'):
        raise PermissionDenied("Permission requise.")
    if montant is None or montant <= Decimal('0.00'):
        raise ValidationError("Le montant doit être strictement positif.")
    if mode not in dict(Paiement.MODES_CHOICES):
        raise ValidationError("Mode de paiement invalide.")

    ordre = OrdrePaiement.objects.select_for_update().get(pk=ordre.pk)

    if ordre.statut == OrdrePaiement.STATUT_ANNULE:
        raise ValidationError("OP annulé : aucun paiement possible.")
    if ordre.statut == OrdrePaiement.STATUT_BROUILLON:
        raise ValidationError("OP non validé : aucun paiement possible.")
    if ordre.cloture_administrative:
        raise ValidationError("OP clôturé : aucun paiement possible.")
    # C1 : seul VALIDE accepte un paiement
    if ordre.statut != OrdrePaiement.STATUT_VALIDE:
        raise ValidationError(
            f"Seul un OP VALIDE peut recevoir un paiement (statut = {ordre.statut})."
        )

    net_actuel = _recalcul_net(ordre)
    if net_actuel + montant > ordre.montant_total:
        raise ValidationError(
            f"Plafond dépassé : net actuel {net_actuel} + {montant} "
            f"> total {ordre.montant_total}."
        )

    paiement = Paiement.objects.create(
        ordre_paiement=ordre,
        montant=montant,
        date_paiement=date_paiement or timezone.now(),
        mode_paiement=mode,
        reference=reference,
        statut=Paiement.STATUT_ENREGISTRE,
        id_utilisateur_enregistreur=user,
    )

    net_apres = net_actuel + montant
    ordre.montant_net_paye = net_apres
    update_fields = ['montant_net_paye']
    if net_apres == ordre.montant_total:
        ordre.statut = OrdrePaiement.STATUT_PAYE
        update_fields.append('statut')
    ordre.save(update_fields=update_fields)

    journaliser(
        user=user, action=JournalAudit.ACTION_CREATION,
        entite='paiements.Paiement', id_entite=paiement.pk,
        apres={
            'ordre_pk': ordre.pk,
            'montant': str(montant),
            'mode': mode,
            'net_apres': str(net_apres),
        },
        commentaire='Enregistrement paiement',
    )
    return paiement


@transaction.atomic
def annuler_paiement(paiement, user, motif):
    """
    Annule un paiement. C2 : refuse si l'OP est clôturé.
    Recalcule le net et ramène l'OP à VALIDE si net < total.
    """
    if not user.has_perm('paiements.annuler_paiement'):
        raise PermissionDenied("Permission requise.")
    if not motif or not motif.strip():
        raise ValidationError("Motif obligatoire.")

    ordre = OrdrePaiement.objects.select_for_update().get(
        pk=paiement.ordre_paiement_id
    )
    paiement = Paiement.objects.select_for_update().get(pk=paiement.pk)

    if paiement.statut != Paiement.STATUT_ENREGISTRE:
        raise ValidationError("Ce paiement est déjà annulé.")
    # C2 : refus si OP clôturé administrativement
    if ordre.cloture_administrative:
        raise ValidationError(
            "OP clôturé administrativement : annulation impossible "
            "sans procédure de régularisation."
        )

    paiement.statut = Paiement.STATUT_ANNULE
    paiement.motif_annulation = motif
    paiement.id_utilisateur_annulateur = user
    paiement.date_annulation = timezone.now()
    paiement.save(update_fields=[
        'statut', 'motif_annulation', 'id_utilisateur_annulateur', 'date_annulation'
    ])

    net = _recalcul_net(ordre)
    ordre.montant_net_paye = net
    update_fields = ['montant_net_paye']
    # Si net < total et statut PAYE → ramener à VALIDE
    if net < ordre.montant_total and ordre.statut == OrdrePaiement.STATUT_PAYE:
        ordre.statut = OrdrePaiement.STATUT_VALIDE
        update_fields.append('statut')
    ordre.save(update_fields=update_fields)

    journaliser(
        user=user, action=JournalAudit.ACTION_ANNULATION,
        entite='paiements.Paiement', id_entite=paiement.pk,
        avant={'statut': 'ENREGISTRE'},
        apres={'statut': 'ANNULE', 'net_apres': str(net)},
        commentaire=motif,
    )
    return paiement


# ---------------------------------------------------------------------
# Confirmations de réception
# ---------------------------------------------------------------------

@transaction.atomic
def confirmer_reception(paiement, user, mode, justificatif,
                        date_confirmation=None):
    """Crée une confirmation de réception."""
    if not user.has_perm('paiements.confirmer_reception'):
        raise PermissionDenied("Permission requise.")
    if mode not in dict(ConfirmationReception.MODES_CHOICES):
        raise ValidationError("Mode invalide.")
    if not justificatif:
        raise ValidationError("Justificatif obligatoire.")

    paiement = Paiement.objects.select_for_update().get(pk=paiement.pk)
    if paiement.statut != Paiement.STATUT_ENREGISTRE:
        raise ValidationError("Ce paiement n'est pas actif.")
    if user.pk == paiement.id_utilisateur_enregistreur_id:
        raise ValidationError(
            "L'utilisateur ayant enregistré le paiement ne peut pas "
            "confirmer sa réception."
        )
    if paiement.confirmations.filter(statut=ConfirmationReception.STATUT_CONFIRME).exists():
        raise ValidationError(
            "Une confirmation active existe déjà pour ce paiement."
        )

    conf = ConfirmationReception.objects.create(
        paiement=paiement,
        date_confirmation=date_confirmation or timezone.now(),
        id_utilisateur_confirmation=user,
        mode=mode,
        justificatif=justificatif,
        statut=ConfirmationReception.STATUT_CONFIRME,
    )

    journaliser(
        user=user, action=JournalAudit.ACTION_CREATION,
        entite='paiements.ConfirmationReception', id_entite=conf.pk,
        apres={'paiement_pk': paiement.pk, 'mode': mode},
        commentaire='Confirmation réception',
    )
    return conf


@transaction.atomic
def annuler_confirmation(confirmation, user, motif):
    """Annule une confirmation. Refus si l'OP est clôturé."""
    if not user.has_perm('paiements.annuler_confirmation'):
        raise PermissionDenied("Permission requise.")
    if not motif or not motif.strip():
        raise ValidationError("Motif obligatoire.")

    confirmation = ConfirmationReception.objects.select_for_update().get(
        pk=confirmation.pk
    )
    if confirmation.statut != ConfirmationReception.STATUT_CONFIRME:
        raise ValidationError("Cette confirmation est déjà annulée.")

    ordre = OrdrePaiement.objects.select_for_update().get(
        pk=confirmation.paiement.ordre_paiement_id
    )
    # C2 : refus si OP clôturé
    if ordre.cloture_administrative:
        raise ValidationError(
            "OP clôturé administrativement : annulation impossible "
            "sans procédure de régularisation."
        )

    confirmation.statut = ConfirmationReception.STATUT_ANNULE
    confirmation.motif_annulation = motif
    confirmation.id_utilisateur_annulateur = user
    confirmation.date_annulation = timezone.now()
    confirmation.save(update_fields=[
        'statut', 'motif_annulation', 'id_utilisateur_annulateur', 'date_annulation'
    ])

    journaliser(
        user=user, action=JournalAudit.ACTION_ANNULATION,
        entite='paiements.ConfirmationReception', id_entite=confirmation.pk,
        avant={'statut': 'CONFIRME'}, apres={'statut': 'ANNULE'},
        commentaire=motif,
    )
    return confirmation


@transaction.atomic
def cloturer_administrativement(ordre, user):
    """Clôture administrative manuelle."""
    if not user.has_perm('paiements.cloturer_ordre_paiement'):
        raise PermissionDenied("Permission requise.")

    ordre = OrdrePaiement.objects.select_for_update().get(pk=ordre.pk)
    if ordre.statut != OrdrePaiement.STATUT_PAYE:
        raise ValidationError("Seul un OP PAYE peut être clôturé.")
    if ordre.cloture_administrative:
        raise ValidationError("OP déjà clôturé.")

    for p in ordre.paiements.filter(statut=Paiement.STATUT_ENREGISTRE):
        if not p.confirmations.filter(
            statut=ConfirmationReception.STATUT_CONFIRME
        ).exists():
            raise ValidationError(
                f"Le paiement #{p.pk} n'a pas de confirmation active."
            )

    ordre.cloture_administrative = True
    ordre.date_cloture = timezone.now()
    ordre.id_utilisateur_cloture = user
    ordre.save(update_fields=[
        'cloture_administrative', 'date_cloture', 'id_utilisateur_cloture'
    ])

    journaliser(
        user=user, action=JournalAudit.ACTION_MODIFICATION,
        entite='paiements.OrdrePaiement', id_entite=ordre.pk,
        avant={'cloture_administrative': False},
        apres={'cloture_administrative': True},
        commentaire='Clôture administrative',
    )
    return ordre
