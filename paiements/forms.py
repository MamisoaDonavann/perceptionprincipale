"""
Formulaires de l'application paiements.
"""

from datetime import date
from decimal import Decimal

from django import forms
from django.utils import timezone

from agents.models import Agent
from decomptes.models import Decompte

from .models import ConfirmationReception, Paiement, PeriodePaiement


def _apply_css(form):
    for field in form.fields.values():
        css = 'form-input'
        if isinstance(field.widget, forms.Select):
            css = 'form-select'
        elif isinstance(field.widget, forms.SelectMultiple):
            css = 'form-select'
        elif isinstance(field.widget, forms.Textarea):
            css = 'form-textarea'
        elif isinstance(field.widget, forms.CheckboxInput):
            css = 'form-checkbox'
        elif isinstance(field.widget, forms.ClearableFileInput):
            css = 'form-input'
        field.widget.attrs.setdefault('class', css)


class OrdrePaiementForm(forms.Form):
    """Formulaire de création d'un ordre de paiement (BROUILLON)."""

    agent = forms.ModelChoiceField(
        queryset=Agent.objects.filter(actif=True),
        label="Agent bénéficiaire",
        required=True,
    )
    annee = forms.IntegerField(
        label="Année",
        min_value=1900,
        max_value=2200,
        initial=date.today().year,
    )
    decomptes = forms.ModelMultipleChoiceField(
        queryset=Decompte.objects.none(),
        label="Décomptes à inclure",
        required=True,
        help_text="Sélectionnez un ou plusieurs décomptes validés du même agent.",
    )
    observation = forms.CharField(
        label="Observation",
        required=False,
        widget=forms.Textarea(attrs={'rows': 3}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        reserved_ids = PeriodePaiement.objects.filter(
            reservation_active=True
        ).values_list('decompte_id', flat=True)
        self.fields['decomptes'].queryset = (
            Decompte.objects.filter(statut=Decompte.STATUT_VALIDE)
            .exclude(pk__in=reserved_ids)
            .select_related('agent')
            .order_by('-annee', '-mois')
        )
        _apply_css(self)

    def clean(self):
        cleaned = super().clean()
        agent = cleaned.get('agent')
        decomptes = cleaned.get('decomptes')
        if agent and decomptes:
            for d in decomptes:
                if d.agent_id != agent.pk:
                    self.add_error(
                        'decomptes',
                        f"Le décompte {d.annee}/{d.mois:02d} "
                        f"appartient à un autre agent."
                    )
        return cleaned


class RetirerPeriodeForm(forms.Form):
    """Retrait d'une période d'un OP BROUILLON."""

    decompte = forms.ModelChoiceField(
        queryset=Decompte.objects.none(),
        label="Décompte à retirer",
        required=True,
    )
    motif = forms.CharField(
        label="Motif",
        required=True,
        widget=forms.Textarea(attrs={'rows': 3}),
    )

    def __init__(self, *args, ordre=None, **kwargs):
        super().__init__(*args, **kwargs)
        if ordre is not None:
            self.fields['decompte'].queryset = (
                Decompte.objects.filter(
                    periodes_paiement__ordre_paiement=ordre,
                    periodes_paiement__reservation_active=True,
                )
            )
        _apply_css(self)


class PaiementForm(forms.Form):
    """Enregistrement d'un paiement (partiel ou complet)."""

    montant = forms.DecimalField(
        label="Montant (Ar)",
        max_digits=14,
        decimal_places=2,
        min_value=Decimal('0.01'),
    )
    mode_paiement = forms.ChoiceField(
        label="Mode de paiement",
        choices=Paiement.MODES_CHOICES,
    )
    date_paiement = forms.DateTimeField(
        label="Date du paiement",
        input_formats=['%Y-%m-%dT%H:%M'],
        widget=forms.DateTimeInput(
            attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'
        ),
        initial=timezone.now,
    )
    reference = forms.CharField(
        label="Référence",
        max_length=100,
        required=False,
        help_text="N° chèque, bordereau, etc. (facultatif).",
    )

    def __init__(self, *args, ordre=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.ordre = ordre
        _apply_css(self)

    def clean_montant(self):
        montant = self.cleaned_data['montant']
        if montant <= 0:
            raise forms.ValidationError(
                "Le montant doit être strictement positif."
            )
        if self.ordre:
            reste = self.ordre.montant_total - self.ordre.montant_net_paye
            if montant > reste:
                raise forms.ValidationError(
                    f"Le montant dépasse le solde restant ({reste} Ar)."
                )
        return montant


class ConfirmationReceptionForm(forms.Form):
    """Confirmation de réception avec justificatif signé."""

    mode = forms.ChoiceField(
        label="Mode de confirmation",
        choices=ConfirmationReception.MODES_CHOICES,
    )
    date_confirmation = forms.DateTimeField(
        label="Date de confirmation",
        input_formats=['%Y-%m-%dT%H:%M'],
        widget=forms.DateTimeInput(
            attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'
        ),
        initial=timezone.now,
    )
    justificatif = forms.FileField(
        label="Justificatif signé",
        required=True,
        help_text="Fichier PDF, JPG ou PNG du justificatif signé.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_css(self)


class MotifForm(forms.Form):
    """Formulaire générique pour saisir un motif d'annulation."""

    motif = forms.CharField(
        label="Motif",
        required=True,
        widget=forms.Textarea(attrs={'rows': 3, 'class': 'form-textarea'}),
    )
