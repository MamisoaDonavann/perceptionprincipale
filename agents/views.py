"""
Vues de l'application agents.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .forms import AgentForm
from .models import Agent


@login_required
@permission_required('agents.view_agent', raise_exception=True)
def agent_list(request):
    """Liste paginée avec recherche et filtres."""
    qs = Agent.objects.all()

    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(
            Q(matricule__icontains=q)
            | Q(nom__icontains=q)
            | Q(prenoms__icontains=q)
            | Q(cin__icontains=q)
        )

    statut = request.GET.get('statut', '').strip()
    if statut in dict(Agent.STATUTS_CHOICES):
        qs = qs.filter(statut_agent=statut)

    actif = request.GET.get('actif', '').strip()
    if actif == '1':
        qs = qs.filter(actif=True)
    elif actif == '0':
        qs = qs.filter(actif=False)

    qs = qs.order_by('nom', 'prenoms')

    paginator = Paginator(qs, 20)
    page = paginator.get_page(request.GET.get('page'))

    return render(request, 'agents/list.html', {
        'page': page,
        'q': q,
        'statut': statut,
        'actif': actif,
        'statuts_choices': Agent.STATUTS_CHOICES,
        'total': qs.count(),
    })


@login_required
@permission_required('agents.view_agent', raise_exception=True)
def agent_detail(request, pk):
    """Fiche détaillée d'un agent."""
    agent = get_object_or_404(Agent, pk=pk)

    affectations = agent.affectations.select_related('unite').order_by('-date_debut')[:10]
    gardes = agent.gardes.select_related('mission', 'tarif').order_by('-date_heure_debut')[:10]
    decomptes = agent.decomptes.order_by('-annee', '-mois')[:10]
    ordres = agent.ordres_paiement.order_by('-annee', '-numero_op')[:10]

    return render(request, 'agents/detail.html', {
        'agent': agent,
        'affectations': affectations,
        'gardes': gardes,
        'decomptes': decomptes,
        'ordres': ordres,
    })


@login_required
@permission_required('agents.add_agent', raise_exception=True)
def agent_create(request):
    """Création d'un nouvel agent."""
    if request.method == 'POST':
        form = AgentForm(request.POST)
        if form.is_valid():
            agent = form.save()
            messages.success(
                request,
                f"Agent {agent.matricule} — {agent.nom} {agent.prenoms} créé."
            )
            return redirect(reverse('agents:detail', args=[agent.pk]))
    else:
        form = AgentForm()

    return render(request, 'agents/form.html', {
        'form': form,
        'titre': "Nouvel agent",
        'mode': 'creation',
        'agent': None,
    })


@login_required
@permission_required('agents.change_agent', raise_exception=True)
def agent_update(request, pk):
    """Modification d'un agent existant."""
    agent = get_object_or_404(Agent, pk=pk)

    if request.method == 'POST':
        form = AgentForm(request.POST, instance=agent)
        if form.is_valid():
            agent = form.save()
            messages.success(
                request,
                f"Agent {agent.matricule} mis à jour."
            )
            return redirect(reverse('agents:detail', args=[agent.pk]))
    else:
        form = AgentForm(instance=agent)

    return render(request, 'agents/form.html', {
        'form': form,
        'titre': f"Modifier {agent.matricule}",
        'mode': 'modification',
        'agent': agent,
    })
