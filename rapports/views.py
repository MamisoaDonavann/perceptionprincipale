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
    generer_decomptes_mensuels_pdf,
    generer_etat_decompte_pdf,
    generer_etat_gardes_excel,
    generer_etat_gardes_pdf,
    generer_historique_agent_excel,
    generer_historique_agent_pdf,
    generer_liste_op_excel,
    generer_liste_op_pdf,
    generer_liste_paiement_pdf,
    generer_rapport_mensuel_pdf,
    generer_rapport_periode_excel,
    generer_rapport_periode_pdf,
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


# ===================================================================
# Rapport 4 — État détaillé des gardes
# ===================================================================

def _filtres_gardes(request):
    """Extrait les filtres GET pour l'état des gardes."""
    from agents.models import Agent
    from missions.models import Mission

    date_debut = _parse_date(request.GET.get('date_debut'), 'de début')
    date_fin = _parse_date(request.GET.get('date_fin'), 'de fin')

    agent = None
    if request.GET.get('agent'):
        try:
            agent = Agent.objects.get(pk=int(request.GET['agent']))
        except (ValueError, Agent.DoesNotExist):
            pass

    mission = None
    if request.GET.get('mission'):
        try:
            mission = Mission.objects.get(pk=int(request.GET['mission']))
        except (ValueError, Mission.DoesNotExist):
            pass

    conforme_raw = request.GET.get('conforme', '').strip()
    conforme = None
    if conforme_raw == '1':
        conforme = True
    elif conforme_raw == '0':
        conforme = False

    return {
        'date_debut': date_debut,
        'date_fin': date_fin,
        'agent': agent,
        'mission': mission,
        'conforme': conforme,
    }


@login_required
def filtres_gardes(request):
    """Formulaire de filtres pour l'état des gardes."""
    verifier_permission(request.user, 'gardes.view_garde')
    from agents.models import Agent
    from missions.models import Mission
    return render(request, 'rapports/filtres_gardes.html', {
        'agents': Agent.objects.filter(actif=True).order_by('nom', 'prenoms'),
        'missions': Mission.objects.order_by('-date_debut')[:100],
        'filtres': _filtres_gardes(request),
    })


@login_required
def etat_gardes_pdf(request):
    verifier_permission(request.user, 'gardes.view_garde')
    try:
        f = _filtres_gardes(request)
        buffer = generer_etat_gardes_pdf(
            f['date_debut'], f['date_fin'],
            f['agent'], f['mission'], f['conforme'],
        )
    except ValidationError as e:
        for msg in e.messages:
            messages.error(request, msg)
        return redirect(reverse('rapports:index'))

    journaliser(
        user=request.user, action=JournalAudit.ACTION_EXPORT,
        entite='gardes.Garde', id_entite=0,
        apres={
            'type': 'etat_gardes_pdf',
            'date_debut': f['date_debut'].isoformat() if f['date_debut'] else None,
            'date_fin': f['date_fin'].isoformat() if f['date_fin'] else None,
            'agent_id': f['agent'].pk if f['agent'] else None,
            'mission_id': f['mission'].pk if f['mission'] else None,
            'conforme': f['conforme'],
        },
        commentaire="Export PDF état des gardes",
    )

    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="etat_gardes.pdf"'
    return response


@login_required
def etat_gardes_excel(request):
    verifier_permission(request.user, 'gardes.view_garde')
    try:
        f = _filtres_gardes(request)
        buffer = generer_etat_gardes_excel(
            f['date_debut'], f['date_fin'],
            f['agent'], f['mission'], f['conforme'],
        )
    except ValidationError as e:
        for msg in e.messages:
            messages.error(request, msg)
        return redirect(reverse('rapports:index'))

    journaliser(
        user=request.user, action=JournalAudit.ACTION_EXPORT,
        entite='gardes.Garde', id_entite=0,
        apres={'type': 'etat_gardes_excel'},
        commentaire="Export Excel état des gardes",
    )

    response = HttpResponse(
        buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = 'attachment; filename="etat_gardes.xlsx"'
    return response


# ===================================================================
# Rapport 5 — Liste des OP
# ===================================================================

def _filtres_op(request):
    date_debut = _parse_date(request.GET.get('date_debut'), 'de début')
    date_fin = _parse_date(request.GET.get('date_fin'), 'de fin')
    statut = request.GET.get('statut', '').strip()
    if statut not in dict(OrdrePaiement.STATUTS_CHOICES):
        statut = None
    return {'date_debut': date_debut, 'date_fin': date_fin, 'statut': statut}


@login_required
def filtres_op(request):
    verifier_permission(request.user, 'paiements.consulter_ordre_paiement')
    return render(request, 'rapports/filtres_op.html', {
        'statuts_choices': OrdrePaiement.STATUTS_CHOICES,
        'filtres': _filtres_op(request),
    })


@login_required
def liste_op_pdf(request):
    verifier_permission(request.user, 'paiements.consulter_ordre_paiement')
    try:
        f = _filtres_op(request)
        buffer = generer_liste_op_pdf(f['date_debut'], f['date_fin'], f['statut'])
    except ValidationError as e:
        for msg in e.messages:
            messages.error(request, msg)
        return redirect(reverse('rapports:index'))

    journaliser(
        user=request.user, action=JournalAudit.ACTION_EXPORT,
        entite='paiements.OrdrePaiement', id_entite=0,
        apres={'type': 'liste_op_pdf', **{k: (v.isoformat() if hasattr(v, 'isoformat') else v) for k, v in f.items()}},
        commentaire="Export PDF liste des OP",
    )

    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="liste_op.pdf"'
    return response


@login_required
def liste_op_excel(request):
    verifier_permission(request.user, 'paiements.consulter_ordre_paiement')
    try:
        f = _filtres_op(request)
        buffer = generer_liste_op_excel(f['date_debut'], f['date_fin'], f['statut'])
    except ValidationError as e:
        for msg in e.messages:
            messages.error(request, msg)
        return redirect(reverse('rapports:index'))

    journaliser(
        user=request.user, action=JournalAudit.ACTION_EXPORT,
        entite='paiements.OrdrePaiement', id_entite=0,
        apres={'type': 'liste_op_excel'},
        commentaire="Export Excel liste des OP",
    )

    response = HttpResponse(
        buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = 'attachment; filename="liste_op.xlsx"'
    return response


# ===================================================================
# Rapport 6 — Rapport mensuel
# ===================================================================

@login_required
def rapport_mensuel_pdf(request, annee, mois):
    verifier_permission(request.user, 'paiements.consulter_ordre_paiement')
    if not (1900 <= annee <= 2200) or not (1 <= mois <= 12):
        messages.error(request, "Année ou mois invalide.")
        return redirect(reverse('rapports:index'))

    buffer = generer_rapport_mensuel_pdf(annee, mois)

    journaliser(
        user=request.user, action=JournalAudit.ACTION_EXPORT,
        entite='rapports.RapportMensuel', id_entite=0,
        apres={'type': 'rapport_mensuel_pdf', 'annee': annee, 'mois': mois},
        commentaire=f"Export PDF rapport mensuel {mois:02d}/{annee}",
    )

    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="rapport_{annee}_{mois:02d}.pdf"'
    return response


# ===================================================================
# Rapport 7 — Rapport sur période
# ===================================================================

def _filtres_periode(request):
    date_debut = _parse_date(request.GET.get('date_debut'), 'de début')
    date_fin = _parse_date(request.GET.get('date_fin'), 'de fin')
    if date_debut is None:
        date_debut = date.today().replace(day=1)
    if date_fin is None:
        date_fin = date.today()
    if date_debut > date_fin:
        raise ValidationError("La date de début doit être antérieure ou égale à la date de fin.")
    return {'date_debut': date_debut, 'date_fin': date_fin}


@login_required
def filtres_periode(request):
    verifier_permission(request.user, 'paiements.consulter_ordre_paiement')
    try:
        f = _filtres_periode(request)
    except ValidationError as e:
        for msg in e.messages:
            messages.error(request, msg)
        f = {'date_debut': None, 'date_fin': None}
    return render(request, 'rapports/filtres_periode.html', {'filtres': f})


@login_required
def rapport_periode_pdf(request):
    verifier_permission(request.user, 'paiements.consulter_ordre_paiement')
    try:
        f = _filtres_periode(request)
        buffer = generer_rapport_periode_pdf(f['date_debut'], f['date_fin'])
    except ValidationError as e:
        for msg in e.messages:
            messages.error(request, msg)
        return redirect(reverse('rapports:index'))

    journaliser(
        user=request.user, action=JournalAudit.ACTION_EXPORT,
        entite='rapports.RapportPeriode', id_entite=0,
        apres={
            'type': 'rapport_periode_pdf',
            'date_debut': f['date_debut'].isoformat(),
            'date_fin': f['date_fin'].isoformat(),
        },
        commentaire=f"Export PDF rapport période {f['date_debut']} → {f['date_fin']}",
    )

    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="rapport_periode.pdf"'
    return response


@login_required
def rapport_periode_excel(request):
    verifier_permission(request.user, 'paiements.consulter_ordre_paiement')
    try:
        f = _filtres_periode(request)
        buffer = generer_rapport_periode_excel(f['date_debut'], f['date_fin'])
    except ValidationError as e:
        for msg in e.messages:
            messages.error(request, msg)
        return redirect(reverse('rapports:index'))

    journaliser(
        user=request.user, action=JournalAudit.ACTION_EXPORT,
        entite='rapports.RapportPeriode', id_entite=0,
        apres={'type': 'rapport_periode_excel'},
        commentaire=f"Export Excel rapport période {f['date_debut']} → {f['date_fin']}",
    )

    response = HttpResponse(
        buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = 'attachment; filename="rapport_periode.xlsx"'
    return response


# ===================================================================
# Récapitulatif mensuel des décomptes (tous agents)
# ===================================================================

@login_required
def filtres_decomptes_mensuels(request):
    """Formulaire de choix de mois pour le récapitulatif mensuel."""
    from datetime import date
    verifier_permission(request.user, 'decomptes.view_decompte')
    return render(request, 'rapports/filtres_decomptes_mensuels.html', {
        'annee_courante': date.today().year,
    })


@login_required
def decomptes_mensuels_pdf(request, annee, mois):
    """Génère le récapitulatif mensuel officiel (tous agents)."""
    verifier_permission(request.user, 'decomptes.view_decompte')

    if not (1900 <= annee <= 2200) or not (1 <= mois <= 12):
        messages.error(request, "Année ou mois invalide.")
        return redirect(reverse('decomptes:list'))

    buffer = generer_decomptes_mensuels_pdf(annee, mois)

    journaliser(
        user=request.user,
        action=JournalAudit.ACTION_EXPORT,
        entite='decomptes.Decompte', id_entite=0,
        apres={
            'type': 'decomptes_mensuels_pdf',
            'annee': annee,
            'mois': mois,
        },
        commentaire=f"Export PDF récapitulatif mensuel {mois:02d}/{annee}",
    )

    filename = f"decomptes_{annee}_{mois:02d}.pdf"
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
