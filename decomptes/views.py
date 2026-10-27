"""
Vues de l'application decomptes.

La création et la validation passent par les services métier.
"""

from datetime import date
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

# Import des modèles nécessaires pour la génération en masse
from agents.models import Agent
from gardes.models import Garde

from .forms import DecompteForm, MOIS_CHOICES # 👈 On importe MOIS_CHOICES
from .models import Decompte, LigneDecompte
from .services import creer_decompte, valider_decompte


@login_required
@permission_required('decomptes.view_decompte', raise_exception=True)
def decompte_list(request):
    """Liste paginée des décomptes avec filtres."""
    qs = Decompte.objects.select_related(
        'agent', 'id_utilisateur_createur', 'id_utilisateur_validateur'
    )

    # 1. Filtre Recherche
    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(
            Q(agent__matricule__icontains=q)
            | Q(agent__nom__icontains=q)
            | Q(agent__prenoms__icontains=q)
        )

    # 2. Filtre Statut
    statut = request.GET.get('statut', '').strip()
    if statut in dict(Decompte.STATUTS_CHOICES):
        qs = qs.filter(statut=statut)

    # 3. Filtre Année
    annee = request.GET.get('annee', '').strip()
    if annee.isdigit():
        qs = qs.filter(annee=int(annee))

    # 4. Filtre Mois (NOUVEAU)
    mois = request.GET.get('mois', '').strip()
    if mois.isdigit() and 1 <= int(mois) <= 12:
        qs = qs.filter(mois=int(mois))

    qs = qs.order_by('-annee', '-mois', 'agent__nom')

    paginator = Paginator(qs, 20)
    page = paginator.get_page(request.GET.get('page'))

    return render(request, 'decomptes/list.html', {
        'page': page,
        'q': q,
        'statut': statut,
        'annee': annee,
        'mois': mois,               # 👈 On passe le mois sélectionné
        'mois_choices': MOIS_CHOICES, # 👈 On passe la liste des mois
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


@login_required
@permission_required('decomptes.add_decompte', raise_exception=True)
def decompte_generer_masse(request):
    """Génère les décomptes de tous les agents pour un mois donné."""
    if request.method == 'POST':
        try:
            annee = int(request.POST.get('annee_masse'))
            mois = int(request.POST.get('mois_masse'))
        except (ValueError, TypeError):
            messages.error(request, "Veuillez sélectionner une année et un mois valides.")
            return redirect('decomptes:list')

        agents = Agent.objects.filter(actif=True)
        total_crees = 0
        total_ignores = 0

        for agent in agents:
            # On vérifie si l'agent a au moins une garde valide et conforme ce mois-ci
            gardes_existent = Garde.objects.filter(
                agent=agent,
                statut=Garde.STATUT_VALIDEE,
                conforme=True,
                date_heure_debut__year=annee,
                date_heure_debut__month=mois
            ).exists()

            if gardes_existent:
                try:
                    # On tente de créer le décompte
                    creer_decompte(agent=agent, annee=annee, mois=mois, user=request.user)
                    total_crees += 1
                except ValidationError:
                    # Le décompte existe déjà pour ce mois, ou autre erreur de validation
                    total_ignores += 1
            else:
                # L'agent n'a pas de gardes pour ce mois
                total_ignores += 1

        messages.success(
            request, 
            f"Génération terminée : {total_crees} décompte(s) créé(s). "
            f"{total_ignores} agent(s) ignoré(s) (pas de gardes ou décompte déjà existant)."
        )
        return redirect('decomptes:list')

    return redirect('decomptes:list')
