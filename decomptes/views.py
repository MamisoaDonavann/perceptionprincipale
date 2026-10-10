"""
Vues de l'application decomptes.

La création et la validation passent par les services métier.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .forms import DecompteForm
from .models import Decompte, LigneDecompte
from .services import creer_decompte, valider_decompte


@login_required
@permission_required('decomptes.view_decompte', raise_exception=True)
def decompte_list(request):
    """Liste paginée des décomptes."""
    qs = Decompte.objects.select_related(
        'agent', 'id_utilisateur_createur', 'id_utilisateur_validateur'
    )

    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(
            Q(agent__matricule__icontains=q)
            | Q(agent__nom__icontains=q)
            | Q(agent__prenoms__icontains=q)
        )

    statut = request.GET.get('statut', '').strip()
    if statut in dict(Decompte.STATUTS_CHOICES):
        qs = qs.filter(statut=statut)

    annee = request.GET.get('annee', '').strip()
    if annee.isdigit():
        qs = qs.filter(annee=int(annee))

    qs = qs.order_by('-annee', '-mois', 'agent__nom')

    paginator = Paginator(qs, 20)
    page = paginator.get_page(request.GET.get('page'))

    return render(request, 'decomptes/list.html', {
        'page': page,
        'q': q,
        'statut': statut,
        'annee': annee,
        'statuts_choices': Decompte.STATUTS_CHOICES,
        'total': qs.count(),
    })


@login_required
@permission_required('decomptes.view_decompte', raise_exception=True)
def decompte_detail(request, pk):
    """Fiche détaillée d'un décompte avec ses lignes figées."""
    decompte = get_object_or_404(
        Decompte.objects.select_related(
            'agent', 'id_utilisateur_createur', 'id_utilisateur_validateur'
        ),
        pk=pk,
    )
    lignes = decompte.lignes.select_related('garde', 'tarif', 'garde__agent').order_by(
        'garde__date_heure_debut'
    )

    return render(request, 'decomptes/detail.html', {
        'decompte': decompte,
        'lignes': lignes,
    })


@login_required
@permission_required('decomptes.add_decompte', raise_exception=True)
def decompte_create(request):
    """Création d'un décompte via le service `creer_decompte`."""
    if request.method == 'POST':
        form = DecompteForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            try:
                decompte, avertissements = creer_decompte(
                    agent=data['agent'],
                    annee=data['annee'],
                    mois=data['mois'],
                    user=request.user,
                )
                for avert in avertissements:
                    messages.warning(request, avert)
                messages.success(
                    request,
                    f"Décompte créé : {decompte.montant_total} Ar "
                    f"({decompte.nombre_gardes_retunes} garde(s))."
                )
                return redirect(reverse('decomptes:detail', args=[decompte.pk]))

            except ValidationError as e:
                if hasattr(e, 'message_dict'):
                    for field, errors in e.message_dict.items():
                        for err in errors:
                            messages.error(request, f"{field} : {err}")
                else:
                    for msg in e.messages:
                        messages.error(request, msg)
    else:
        form = DecompteForm()

    return render(request, 'decomptes/form.html', {
        'form': form,
        'titre': "Nouveau décompte mensuel",
    })


@login_required
@permission_required('decomptes.change_decompte', raise_exception=True)
def decompte_valider(request, pk):
    """Validation d'un décompte BROUILLON via le service `valider_decompte`."""
    decompte = get_object_or_404(Decompte, pk=pk)

    if request.method == 'POST':
        try:
            valider_decompte(decompte, request.user)
            messages.success(request, "Décompte validé.")
            return redirect(reverse('decomptes:detail', args=[decompte.pk]))
        except ValidationError as e:
            for msg in e.messages:
                messages.error(request, msg)

    return render(request, 'decomptes/valider.html', {
        'decompte': decompte,
    })
