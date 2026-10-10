"""
Vues de l'application rapports.

Génération PDF/Excel en mémoire. Contrôle des permissions côté serveur.
"""

from datetime import date, datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from agents.models import Agent
from audit.models import JournalAudit
from audit.services import journaliser
from decomptes.models import Decompte
from paiements.models import OrdrePaiement

from .permissions import verifier_permission
from .services import (
    generer_etat_decompte_pdf,
    generer_historique_agent_excel,
    generer_historique_agent_pdf,
    generer_liste_paiement_pdf,
)


# ===================================================================
# Index
# ===================================================================

@login_required
def index(request):
    """Page de sélection des rapports."""
    return render(request, 'rapports/index.html', {
        'peut_etat_decompte': request.user.has_perm('decomptes.view_decompte'),
        'peut_liste_paiement': request.user.has_perm('paiements.consulter_ordre_paiement'),
        'peut_historique_agent': request.user.has_perm('agents.view_agent'),
    })


# ===================================================================
# Rapport 1 — État de décompte (PDF)
# ===================================================================

@login_required
def etat_decompte_pdf(request, pk):
    verifier_permission(request.user, 'decomptes.view_decompte')
    decompte = get_object_or_404(Decompte, pk=pk)

    if decompte.statut != Decompte.STATUT_VALIDE:
        messages.error(
            request,
            "Seuls les décomptes validés peuvent être exportés."
        )
        return redirect(reverse('decomptes:detail', args=[decompte.pk]))

    buffer = generer_etat_decompte_pdf(decompte)

    journaliser(
        user=request.user,
        action=JournalAudit.ACTION_EXPORT,
        entite='decomptes.Decompte',
        id_entite=decompte.pk,
        apres={
            'type': 'etat_decompte_pdf',
            'annee': decompte.annee,
            'mois': decompte.mois,
            'agent_id': decompte.agent_id,
        },
        commentaire=f"Export PDF état de décompte {decompte.annee}/{decompte.mois:02d}",
    )

    filename = (
        f"decompte_{decompte.agent.matricule}_"
        f"{decompte.annee}_{decompte.mois:02d}.pdf"
    )
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


# ===================================================================
# Rapport 2 — Liste de paiement (PDF)
# ===================================================================

@login_required
def liste_paiement_pdf(request, pk):
    verifier_permission(request.user, 'paiements.consulter_ordre_paiement')
    op = get_object_or_404(OrdrePaiement, pk=pk)

    if op.statut not in (
        OrdrePaiement.STATUT_VALIDE,
        OrdrePaiement.STATUT_PAYE,
    ):
        messages.error(
            request,
            "Seul un OP validé ou payé peut faire l'objet d'une liste de paiement."
        )
        return redirect(reverse('paiements:detail', args=[op.pk]))

    buffer = generer_liste_paiement_pdf(op)

    journaliser(
        user=request.user,
        action=JournalAudit.ACTION_EXPORT,
        entite='paiements.OrdrePaiement',
        id_entite=op.pk,
        apres={
            'type': 'liste_paiement_pdf',
            'numero_op': op.numero_op,
            'agent_id': op.agent_beneficiaire_id,
        },
        commentaire=f"Export PDF liste de paiement {op.numero_op}",
    )

    filename = f"liste_paiement_{op.numero_op.replace('/', '-')}.pdf"
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


# ===================================================================
# Rapport 3 — Historique agent (PDF + Excel)
# ===================================================================

def _parse_date(value, nom_champ):
    """Parse une date ISO. Retourne None si vide. Lève ValidationError si invalide."""
    if not value:
        return None
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except ValueError:
        raise ValidationError(
            f"La date {nom_champ} est invalide (format attendu : AAAA-MM-JJ)."
        )


@login_required
def historique_agent_pdf(request, pk):
    verifier_permission(request.user, 'agents.view_agent')
    agent = get_object_or_404(Agent, pk=pk)

    try:
        date_debut = _parse_date(request.GET.get('date_debut'), 'de début')
        date_fin = _parse_date(request.GET.get('date_fin'), 'de fin')
        buffer = generer_historique_agent_pdf(agent, date_debut, date_fin)
    except ValidationError as e:
        for msg in e.messages:
            messages.error(request, msg)
        return redirect(reverse('rapports:index'))

    journaliser(
        user=request.user,
        action=JournalAudit.ACTION_EXPORT,
        entite='agents.Agent',
        id_entite=agent.pk,
        apres={
            'type': 'historique_agent_pdf',
            'date_debut': date_debut.isoformat() if date_debut else None,
            'date_fin': date_fin.isoformat() if date_fin else None,
        },
        commentaire=f"Export PDF historique agent {agent.matricule}",
    )

    filename = f"historique_{agent.matricule}.pdf"
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
def historique_agent_excel(request, pk):
    verifier_permission(request.user, 'agents.view_agent')
    agent = get_object_or_404(Agent, pk=pk)

    try:
        date_debut = _parse_date(request.GET.get('date_debut'), 'de début')
        date_fin = _parse_date(request.GET.get('date_fin'), 'de fin')
        buffer = generer_historique_agent_excel(agent, date_debut, date_fin)
    except ValidationError as e:
        for msg in e.messages:
            messages.error(request, msg)
        return redirect(reverse('rapports:index'))

    journaliser(
        user=request.user,
        action=JournalAudit.ACTION_EXPORT,
        entite='agents.Agent',
        id_entite=agent.pk,
        apres={
            'type': 'historique_agent_excel',
            'date_debut': date_debut.isoformat() if date_debut else None,
            'date_fin': date_fin.isoformat() if date_fin else None,
        },
        commentaire=f"Export Excel historique agent {agent.matricule}",
    )

    filename = f"historique_{agent.matricule}.xlsx"
    response = HttpResponse(
        buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
