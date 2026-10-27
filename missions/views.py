"""
Vues de l'application missions.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .forms import MissionForm, ParticipationMissionForm
from .models import Mission, ParticipationMission

# 👇 IMPORTS POUR L'AUDIT 👇
from audit.models import JournalAudit
from audit.services import journaliser


@login_required
@permission_required('missions.view_mission', raise_exception=True)
def mission_list(request):
    """Liste paginée des missions avec filtres et recherche."""
    qs = Mission.objects.annotate(
        nb_participants=Count('participations')
    )

    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(
            Q(numero_officiel__icontains=q)
            | Q(libelle__icontains=q)
            | Q(lieu__icontains=q)
        )

    statut = request.GET.get('statut', '').strip()
    if statut in dict(Mission.STATUTS_CHOICES):
        qs = qs.filter(statut=statut)

    qs = qs.order_by('-date_debut')

    paginator = Paginator(qs, 20)
    page = paginator.get_page(request.GET.get('page'))

    return render(request, 'missions/list.html', {
        'page': page,
        'q': q,
        'statut': statut,
        'statuts_choices': Mission.STATUTS_CHOICES,
        'total': qs.count(),
    })


@login_required
@permission_required('missions.view_mission', raise_exception=True)
def mission_detail(request, pk):
    """Fiche détaillée d'une mission avec ses participants (paginés)."""
    mission = get_object_or_404(Mission, pk=pk)

    # 1. On récupère toutes les participations
    participations_list = (
        mission.participations
        .select_related('agent')
        .order_by('agent__nom', 'agent__prenoms')
    )

    # 2. On configure la pagination (5 participants par page)
    paginator = Paginator(participations_list, 5)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    form = ParticipationMissionForm(mission=mission)

    return render(request, 'missions/detail.html', {
        'mission': mission,
        'participations': page_obj, # On passe la page paginée
        'page_obj': page_obj,       # On passe aussi page_obj pour le template
        'form': form,
    })


@login_required
@permission_required('missions.add_mission', raise_exception=True)
def mission_create(request):
    """Création d'une nouvelle mission."""
    if request.method == 'POST':
        form = MissionForm(request.POST)
        if form.is_valid():
            mission = form.save()
            
            # 👇 AJOUT JOURNALISATION CREATION 👇
            journaliser(
                user=request.user,
                action=JournalAudit.ACTION_CREATION,
                entite='missions.Mission',
                id_entite=mission.pk,
                apres={'libelle': mission.libelle, 'lieu': mission.lieu},
                commentaire=f"Création de la mission « {mission.libelle} »",
            )
            
            messages.success(
                request,
                f"Mission « {mission.libelle} » créée."
            )
            return redirect(reverse('missions:detail', args=[mission.pk]))
    else:
        form = MissionForm()

    return render(request, 'missions/form.html', {
        'form': form,
        'titre': "Nouvelle mission",
        'mode': 'creation',
        'mission': None,
    })


@login_required
@permission_required('missions.change_mission', raise_exception=True)
def mission_update(request, pk):
    """Modification d'une mission existante."""
    mission = get_object_or_404(Mission, pk=pk)

    if request.method == 'POST':
        form = MissionForm(request.POST, instance=mission)
        if form.is_valid():
            mission = form.save()
            
            # 👇 AJOUT JOURNALISATION MODIFICATION 👇
            journaliser(
                user=request.user,
                action=JournalAudit.ACTION_MODIFICATION,
                entite='missions.Mission',
                id_entite=mission.pk,
                commentaire=f"Modification de la mission « {mission.libelle} »",
            )
            
            messages.success(
                request,
                f"Mission « {mission.libelle} » mise à jour."
            )
            return redirect(reverse('missions:detail', args=[mission.pk]))
    else:
        form = MissionForm(instance=mission)

    return render(request, 'missions/form.html', {
        'form': form,
        'titre': f"Modifier — {mission.libelle}",
        'mode': 'modification',
        'mission': mission,
    })


@login_required
@permission_required('missions.add_participationmission', raise_exception=True)
def participation_create(request, pk):
    """Ajoute un participant à une mission."""
    mission = get_object_or_404(Mission, pk=pk)

    if request.method == 'POST':
        form = ParticipationMissionForm(request.POST, mission=mission)
        if form.is_valid():
            participation = form.save(commit=False)
            participation.mission = mission
            try:
                participation.full_clean()
                participation.save()
                
                # 👇 AJOUT JOURNALISATION AJOUT PARTICIPANT 👇
                journaliser(
                    user=request.user,
                    action=JournalAudit.ACTION_MODIFICATION,
                    entite='missions.Mission',
                    id_entite=mission.pk,
                    commentaire=f"Ajout du participant {participation.agent.nom} {participation.agent.prenoms} à la mission",
                )
                
                messages.success(
                    request,
                    f"{participation.agent.nom} {participation.agent.prenoms} "
                    f"ajouté à la mission."
                )
            except Exception as e:
                messages.error(request, f"Erreur : {e}")
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field} : {error}")

    return redirect(reverse('missions:detail', args=[mission.pk]))


@login_required
@permission_required('missions.change_participationmission', raise_exception=True)
@require_POST
def participation_delete(request, pk, participation_pk):
    """Retire un participant d'une mission."""
    mission = get_object_or_404(Mission, pk=pk)
    participation = get_object_or_404(
        ParticipationMission, pk=participation_pk, mission=mission
    )
    agent_nom = f"{participation.agent.nom} {participation.agent.prenoms}"
    
    # On sauvegarde l'ID de l'agent avant de le supprimer
    agent_id = participation.agent.pk
    
    participation.delete()
    
    # 👇 AJOUT JOURNALISATION RETRAIT PARTICIPANT 👇
    journaliser(
        user=request.user,
        action=JournalAudit.ACTION_MODIFICATION,
        entite='missions.Mission',
        id_entite=mission.pk,
        commentaire=f"Retrait du participant {agent_nom} de la mission",
    )
    
    messages.success(request, f"{agent_nom} retiré de la mission.")
    return redirect(reverse('missions:detail', args=[mission.pk]))
