"""
Vues de l'application tarifs.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from gardes.models import Garde

from .forms import TarifForm
from .models import Tarif


@login_required
@permission_required('tarifs.view_tarif', raise_exception=True)
def tarif_list(request):
    """Liste paginée des tarifs avec filtre d'activation."""
    qs = Tarif.objects.all().select_related('id_utilisateur_createur')

    actif = request.GET.get('actif', '').strip()
    if actif == '1':
        qs = qs.filter(actif=True)
    elif actif == '0':
        qs = qs.filter(actif=False)

    qs = qs.order_by('-date_debut_validite')

    paginator = Paginator(qs, 20)
    page = paginator.get_page(request.GET.get('page'))

    return render(request, 'tarifs/list.html', {
        'page': page,
        'actif': actif,
        'total': qs.count(),
    })


@login_required
@permission_required('tarifs.view_tarif', raise_exception=True)
def tarif_detail(request, pk):
    """Fiche détaillée d'un tarif."""
    tarif = get_object_or_404(
        Tarif.objects.select_related('id_utilisateur_createur'), pk=pk
    )

    gardes_liees = (
        Garde.objects
        .filter(tarif=tarif)
        .select_related('agent', 'mission')
        .order_by('-date_heure_debut')[:20]
    )
    nb_gardes = Garde.objects.filter(tarif=tarif).count()
    utilisable = nb_gardes == 0

    return render(request, 'tarifs/detail.html', {
        'tarif': tarif,
        'gardes_liees': gardes_liees,
        'nb_gardes': nb_gardes,
        'utilisable': utilisable,
    })


@login_required
@permission_required('tarifs.add_tarif', raise_exception=True)
def tarif_create(request):
    """Création d'un nouveau tarif."""
    if request.method == 'POST':
        form = TarifForm(request.POST)
        if form.is_valid():
            tarif = form.save(commit=False)
            tarif.id_utilisateur_createur = request.user
            tarif.save()
            messages.success(
                request,
                f"Tarif {tarif.montant_partiel} Ar créé."
            )
            return redirect(reverse('tarifs:detail', args=[tarif.pk]))
    else:
        form = TarifForm()

    return render(request, 'tarifs/form.html', {
        'form': form,
        'titre': "Nouveau tarif",
        'mode': 'creation',
        'tarif': None,
    })


@login_required
@permission_required('tarifs.change_tarif', raise_exception=True)
def tarif_update(request, pk):
    """
    Modification d'un tarif existant.

    Interdit si le tarif est déjà utilisé par une ou plusieurs gardes.
    """
    tarif = get_object_or_404(Tarif, pk=pk)

    if Garde.objects.filter(tarif=tarif).exists():
        messages.error(
            request,
            "Ce tarif est utilisé par des gardes existantes. "
            "Créez un nouveau tarif plutôt que de modifier celui-ci."
        )
        return redirect(reverse('tarifs:detail', args=[tarif.pk]))

    if request.method == 'POST':
        form = TarifForm(request.POST, instance=tarif)
        if form.is_valid():
            tarif = form.save()
            messages.success(
                request,
                f"Tarif {tarif.montant_partiel} Ar mis à jour."
            )
            return redirect(reverse('tarifs:detail', args=[tarif.pk]))
    else:
        form = TarifForm(instance=tarif)

    return render(request, 'tarifs/form.html', {
        'form': form,
        'titre': f"Modifier le tarif #{tarif.pk}",
        'mode': 'modification',
        'tarif': tarif,
    })


@login_required
@permission_required('tarifs.change_tarif', raise_exception=True)
@require_POST
def tarif_toggle_actif(request, pk):
    """Active ou désactive un tarif (sans suppression)."""
    tarif = get_object_or_404(Tarif, pk=pk)
    tarif.actif = not tarif.actif
    tarif.save(update_fields=['actif'])

    etat = "activé" if tarif.actif else "désactivé"
    messages.success(request, f"Tarif {etat}.")

    return redirect(reverse('tarifs:detail', args=[tarif.pk]))
