"""
Vues de l'application paiements.

Toutes les opérations sensibles passent par les services métier.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .forms import (
    ConfirmationReceptionForm, MotifForm, OrdrePaiementForm,
    PaiementForm, RetirerPeriodeForm,
)
from .models import ConfirmationReception, OrdrePaiement, Paiement
from .services import (
    annuler_confirmation, annuler_ordre_paiement, annuler_paiement,
    cloturer_administrativement, confirmer_reception,
    creer_ordre_paiement, enregistrer_paiement,
    retirer_periode_ordre, valider_ordre_paiement,
)


def _handle_validation_error(request, e):
    """Convertit une ValidationError en messages utilisateur."""
    if hasattr(e, 'message_dict'):
        for field, errors in e.message_dict.items():
            for err in errors:
                messages.error(request, f"{field} : {err}")
    else:
        for msg in e.messages:
            messages.error(request, msg)


# -------------------------------------------------------------------
# Ordres de paiement
# -------------------------------------------------------------------

@login_required
@permission_required('paiements.consulter_ordre_paiement', raise_exception=True)
def op_list(request):
    """Liste paginée des ordres de paiement."""
    qs = OrdrePaiement.objects.select_related(
        'agent_beneficiaire', 'id_utilisateur_createur', 'id_utilisateur_validateur'
    )

    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(
            Q(numero_op__icontains=q)
            | Q(agent_beneficiaire__matricule__icontains=q)
            | Q(agent_beneficiaire__nom__icontains=q)
        )

    statut = request.GET.get('statut', '').strip()
    if statut in dict(OrdrePaiement.STATUTS_CHOICES):
        qs = qs.filter(statut=statut)

    annee = request.GET.get('annee', '').strip()
    if annee.isdigit():
        qs = qs.filter(annee=int(annee))

    qs = qs.order_by('-annee', '-numero_op')

    paginator = Paginator(qs, 20)
    page = paginator.get_page(request.GET.get('page'))

    return render(request, 'paiements/list.html', {
        'page': page,
        'q': q,
        'statut': statut,
        'annee': annee,
        'statuts_choices': OrdrePaiement.STATUTS_CHOICES,
        'total': qs.count(),
    })


@login_required
@permission_required('paiements.consulter_ordre_paiement', raise_exception=True)
def op_detail(request, pk):
    """Fiche détaillée d'un OP."""
    op = get_object_or_404(
        OrdrePaiement.objects.select_related(
            'agent_beneficiaire', 'id_utilisateur_createur',
            'id_utilisateur_validateur', 'id_utilisateur_cloture',
        ),
        pk=pk,
    )
    periodes = op.periodes.select_related('decompte').order_by(
        'decompte__annee', 'decompte__mois'
    )
    paiements = op.paiements.select_related(
        'id_utilisateur_enregistreur', 'id_utilisateur_annulateur'
    ).order_by('-date_paiement')

    paiements_actifs = paiements.filter(statut=Paiement.STATUT_ENREGISTRE)
    for p in paiements_actifs:
        p.confirmation_active = p.confirmations.filter(
            statut=ConfirmationReception.STATUT_CONFIRME
        ).first()

    return render(request, 'paiements/detail.html', {
        'op': op,
        'periodes': periodes,
        'paiements': paiements,
        'paiements_actifs': paiements_actifs,
        'peut_payer': op.statut == OrdrePaiement.STATUT_VALIDE,
        'peut_valider': op.statut == OrdrePaiement.STATUT_BROUILLON,
        'peut_annuler': op.statut in (
            OrdrePaiement.STATUT_BROUILLON,
            OrdrePaiement.STATUT_VALIDE,
            OrdrePaiement.STATUT_PAYE,
        ) and not op.paiements.filter(statut=Paiement.STATUT_ENREGISTRE).exists(),
        'peut_cloturer': (
            op.statut == OrdrePaiement.STATUT_PAYE
            and not op.cloture_administrative
        ),
    })


@login_required
@permission_required('paiements.creer_ordre_paiement', raise_exception=True)
def op_create(request):
    """Création d'un OP BROUILLON via le service `creer_ordre_paiement`."""
    if request.method == 'POST':
        form = OrdrePaiementForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            try:
                op, avertissements = creer_ordre_paiement(
                    agent=data['agent'],
                    annee=data['annee'],
                    decomptes=list(data['decomptes']),
                    user=request.user,
                    observation=data.get('observation') or '',
                )
                for a in avertissements:
                    messages.warning(request, a)
                messages.success(
                    request,
                    f"Ordre de paiement {op.numero_op} créé — "
                    f"{op.montant_total} Ar."
                )
                return redirect(reverse('paiements:detail', args=[op.pk]))
            except ValidationError as e:
                _handle_validation_error(request, e)
    else:
        form = OrdrePaiementForm()

    return render(request, 'paiements/form.html', {
        'form': form,
        'titre': "Nouvel ordre de paiement",
    })


@login_required
@permission_required('paiements.valider_ordre_paiement', raise_exception=True)
def op_valider(request, pk):
    """Validation d'un OP BROUILLON."""
    op = get_object_or_404(OrdrePaiement, pk=pk)
    if request.method == 'POST':
        try:
            valider_ordre_paiement(op, request.user)
            messages.success(request, f"OP {op.numero_op} validé.")
            return redirect(reverse('paiements:detail', args=[op.pk]))
        except ValidationError as e:
            _handle_validation_error(request, e)

    return render(request, 'paiements/valider.html', {'op': op})


@login_required
@permission_required('paiements.creer_ordre_paiement', raise_exception=True)
def op_retirer_periode(request, pk):
    """Retire une période d'un OP BROUILLON."""
    op = get_object_or_404(OrdrePaiement, pk=pk)
    if op.statut != OrdrePaiement.STATUT_BROUILLON:
        messages.error(request, "Seul un OP BROUILLON peut être modifié.")
        return redirect(reverse('paiements:detail', args=[op.pk]))

    if request.method == 'POST':
        form = RetirerPeriodeForm(request.POST, ordre=op)
        if form.is_valid():
            try:
                retirer_periode_ordre(
                    op,
                    form.cleaned_data['decompte'],
                    request.user,
                    form.cleaned_data['motif'],
                )
                messages.success(request, "Période retirée.")
                return redirect(reverse('paiements:detail', args=[op.pk]))
            except ValidationError as e:
                _handle_validation_error(request, e)
    else:
        form = RetirerPeriodeForm(ordre=op)

    return render(request, 'paiements/retirer_periode.html', {
        'op': op, 'form': form,
    })


@login_required
@permission_required('paiements.annuler_ordre_paiement', raise_exception=True)
def op_annuler(request, pk):
    """Annulation contrôlée d'un OP."""
    op = get_object_or_404(OrdrePaiement, pk=pk)

    if request.method == 'POST':
        form = MotifForm(request.POST)
        if form.is_valid():
            try:
                annuler_ordre_paiement(op, request.user, form.cleaned_data['motif'])
                messages.success(request, f"OP {op.numero_op} annulé.")
                return redirect(reverse('paiements:detail', args=[op.pk]))
            except ValidationError as e:
                _handle_validation_error(request, e)
    else:
        form = MotifForm()

    return render(request, 'paiements/annuler.html', {
        'op': op, 'form': form,
    })


@login_required
@permission_required('paiements.cloturer_ordre_paiement', raise_exception=True)
def op_cloturer(request, pk):
    """Clôture administrative."""
    op = get_object_or_404(OrdrePaiement, pk=pk)

    if request.method == 'POST':
        try:
            cloturer_administrativement(op, request.user)
            messages.success(request, f"OP {op.numero_op} clôturé administrativement.")
            return redirect(reverse('paiements:detail', args=[op.pk]))
        except ValidationError as e:
            _handle_validation_error(request, e)

    return render(request, 'paiements/cloturer.html', {'op': op})


# -------------------------------------------------------------------
# Paiements
# -------------------------------------------------------------------

@login_required
@permission_required('paiements.enregistrer_paiement', raise_exception=True)
def paiement_create(request, pk):
    """Enregistrement d'un paiement sur un OP VALIDE."""
    op = get_object_or_404(OrdrePaiement, pk=pk)

    if request.method == 'POST':
        form = PaiementForm(request.POST, ordre=op)
        if form.is_valid():
            data = form.cleaned_data
            try:
                enregistrer_paiement(
                    op,
                    montant=data['montant'],
                    mode=data['mode_paiement'],
                    user=request.user,
                    date_paiement=data['date_paiement'],
                    reference=data.get('reference') or '',
                )
                messages.success(
                    request,
                    f"Paiement de {data['montant']} Ar enregistré sur {op.numero_op}."
                )
                return redirect(reverse('paiements:detail', args=[op.pk]))
            except ValidationError as e:
                _handle_validation_error(request, e)
    else:
        form = PaiementForm(ordre=op)

    return render(request, 'paiements/paiement_form.html', {
        'op': op, 'form': form,
    })


@login_required
@permission_required('paiements.annuler_paiement', raise_exception=True)
def paiement_annuler(request, pk, paiement_pk):
    """Annulation d'un paiement."""
    op = get_object_or_404(OrdrePaiement, pk=pk)
    paiement = get_object_or_404(Paiement, pk=paiement_pk, ordre_paiement=op)

    if request.method == 'POST':
        form = MotifForm(request.POST)
        if form.is_valid():
            try:
                annuler_paiement(paiement, request.user, form.cleaned_data['motif'])
                messages.success(request, "Paiement annulé.")
                return redirect(reverse('paiements:detail', args=[op.pk]))
            except ValidationError as e:
                _handle_validation_error(request, e)
    else:
        form = MotifForm()

    return render(request, 'paiements/paiement_annuler.html', {
        'op': op, 'paiement': paiement, 'form': form,
    })


# -------------------------------------------------------------------
# Confirmations
# -------------------------------------------------------------------

@login_required
@permission_required('paiements.confirmer_reception', raise_exception=True)
def confirmation_create(request, pk, paiement_pk):
    """Enregistrement d'une confirmation de réception."""
    op = get_object_or_404(OrdrePaiement, pk=pk)
    paiement = get_object_or_404(Paiement, pk=paiement_pk, ordre_paiement=op)

    if request.method == 'POST':
        form = ConfirmationReceptionForm(request.POST, request.FILES)
        if form.is_valid():
            data = form.cleaned_data
            try:
                confirmer_reception(
                    paiement,
                    user=request.user,
                    mode=data['mode'],
                    justificatif=data['justificatif'],
                    date_confirmation=data['date_confirmation'],
                )
                messages.success(request, "Confirmation de réception enregistrée.")
                return redirect(reverse('paiements:detail', args=[op.pk]))
            except ValidationError as e:
                _handle_validation_error(request, e)
    else:
        form = ConfirmationReceptionForm()

    return render(request, 'paiements/confirmation_form.html', {
        'op': op, 'paiement': paiement, 'form': form,
    })


@login_required
@permission_required('paiements.annuler_confirmation', raise_exception=True)
def confirmation_annuler(request, pk, paiement_pk, confirmation_pk):
    """Annulation d'une confirmation."""
    op = get_object_or_404(OrdrePaiement, pk=pk)
    paiement = get_object_or_404(Paiement, pk=paiement_pk, ordre_paiement=op)
    confirmation = get_object_or_404(
        ConfirmationReception, pk=confirmation_pk, paiement=paiement
    )

    if request.method == 'POST':
        form = MotifForm(request.POST)
        if form.is_valid():
            try:
                annuler_confirmation(confirmation, request.user, form.cleaned_data['motif'])
                messages.success(request, "Confirmation annulée.")
                return redirect(reverse('paiements:detail', args=[op.pk]))
            except ValidationError as e:
                _handle_validation_error(request, e)
    else:
        form = MotifForm()

    return render(request, 'paiements/confirmation_annuler.html', {
        'op': op, 'paiement': paiement,
        'confirmation': confirmation, 'form': form,
    })
