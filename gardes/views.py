"""
Vues de l'application gardes.

La création d'une garde passe obligatoirement par le service
`gardes.services.creer_garde()`.
L'annulation passe par `gardes.services.annuler_garde()`.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from agents.models import Agent

from .forms import AnnulationGardeForm, GardeForm
from .models import Garde
from .services import annuler_garde, creer_garde


@login_required
@permission_required('gardes.view_garde', raise_exception=True)
def garde_list(request):
    """Liste paginée des gardes avec filtres."""
    qs = Garde.objects.select_related('agent', 'mission', 'tarif')

    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(
            Q(agent__matricule__icontains=q)
            | Q(agent__nom__icontains=q)
            | Q(agent__prenoms__icontains=q)
            | Q(mission__numero_officiel__icontains=q)
            | Q(mission__libelle__icontains=q)
        )

    statut = request.GET.get('statut', '').strip()
    if statut in dict(Garde.STATUTS_CHOICES):
        qs = qs.filter(statut=statut)

    conforme = request.GET.get('conforme', '').strip()
    if conforme == '1':
        qs = qs.filter(conforme=True)
    elif conforme == '0':
        qs = qs.filter(conforme=False)

    qs = qs.order_by('-date_heure_debut')

    paginator = Paginator(qs, 20)
    page = paginator.get_page(request.GET.get('page'))

    return render(request, 'gardes/list.html', {
        'page': page,
        'q': q,
        'statut': statut,
        'conforme': conforme,
        'statuts_choices': Garde.STATUTS_CHOICES,
        'total': qs.count(),
    })


@login_required
@permission_required('gardes.view_garde', raise_exception=True)
def garde_detail(request, pk):
    """Fiche détaillée d'une garde."""
    garde = get_object_or_404(
        Garde.objects.select_related('agent', 'mission', 'tarif', 'id_utilisateur_saisie'),
        pk=pk,
    )
    form_annulation = AnnulationGardeForm()
    return render(request, 'gardes/detail.html', {
        'garde': garde,
        'form_annulation': form_annulation,
    })


@login_required
@permission_required('gardes.add_garde', raise_exception=True)
def garde_create(request):
    """
    Création d'une garde via le service `creer_garde`.

    Le formulaire valide les champs bruts. Le service effectue :
    - le calcul de la durée et des partiels,
    - la vérification de conformité,
    - la sélection du tarif applicable,
    - la détection des chevauchements,
    - la journalisation.
    """
    if request.method == 'POST':
        form = GardeForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            try:
                garde, avertissements = creer_garde(
                    user=request.user,
                    agent=data['agent'],
                    date_heure_debut=data['date_heure_debut'],
                    date_heure_fin=data['date_heure_fin'],
                    tarif=data.get('tarif') or None,
                    mission=data.get('mission') or None,
                    observation=data.get('observation') or None,
                )

                for avert in avertissements:
                    messages.warning(request, avert)

                if not garde.conforme:
                    messages.warning(
                        request,
                        f"Garde non conforme : {garde.motif_anomalie}. "
                        "Elle est enregistrée mais sera exclue des décomptes."
                    )

                messages.success(
                    request,
                    f"Garde enregistrée pour {garde.agent.nom} "
                    f"{garde.agent.prenoms}."
                )
                return redirect(reverse('gardes:detail', args=[garde.pk]))

            except ValidationError as e:
                if hasattr(e, 'message_dict'):
                    for field, errors in e.message_dict.items():
                        for err in errors:
                            messages.error(request, f"{field} : {err}")
                else:
                    for msg in e.messages:
                        messages.error(request, msg)
    else:
        form = GardeForm()

    return render(request, 'gardes/form.html', {
        'form': form,
        'titre': "Nouvelle garde",
    })


@login_required
@permission_required('gardes.change_garde', raise_exception=True)
def garde_annuler(request, pk):
    """
    Annulation d'une garde via le service `annuler_garde`.
    """
    garde = get_object_or_404(Garde, pk=pk)

    if request.method == 'POST':
        form = AnnulationGardeForm(request.POST)
        if form.is_valid():
            try:
                annuler_garde(request.user, garde, motif=form.cleaned_data['motif'])
                messages.success(request, "Garde annulée.")
                return redirect(reverse('gardes:detail', args=[garde.pk]))
            except ValidationError as e:
                for msg in e.messages:
                    messages.error(request, msg)
    else:
        form = AnnulationGardeForm()

    return render(request, 'gardes/annuler.html', {
        'garde': garde,
        'form': form,
    })
