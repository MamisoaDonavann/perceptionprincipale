"""
Formulaires de l'application paiements.
"""

from datetime import date
from decimal import Decimal

from django import forms
from django.utils import timezone

from agents.models import Agent
from decomptes.models import Decompte

from .models import (
    ConfirmationReception, OrdrePaiement, Paiement, PeriodePaiement,
)


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

    # 👇 CHAMP NUMÉRO OP MANUEL 👇
    numero_op = forms.CharField(
        label="Numéro de l'OP",
        max_length=50,
        required=True,
        help_text="Saisissez le numéro officiel (ex: OP-2026-0001).",
        widget=forms.TextInput(attrs={'placeholder': 'OP-2026-XXXX'})
    )

    agent = forms.ModelChoiceField(
        queryset=Agent.objects.filter(actif=True),
        label="Agent bénéficiaire",
        required=True,
        empty_label="Sélectionner un agent...",
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

    # ---- Informations administratives (facultatives) ----
    date_emission = forms.DateField(
        label="Date d'émission",
        required=False,
        input_formats=['%Y-%m-%d'],
        widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
        help_text="Date figurant sur le document officiel.",
    )
    numero_be = forms.CharField(
        label="Numéro BE",
        max_length=50,
        required=False,
    )
    
    # 👇 AMÉLIORATION DES TEXTES D'AIDE 👇
    titulaire_nom = forms.CharField(
        label="Nom du titulaire",
        max_length=200,
        required=False,
        help_text="À remplir uniquement si une autre personne vient retirer l'argent à la place de l'agent (ex: conjoint, ayant droit).",
    )
    titulaire_numero = forms.CharField(
        label="N° d'identification du titulaire",
        max_length=50,
        required=False,
        help_text="CIN de la personne qui retire l'argent (si différente de l'agent).",
    )
    # 👆 FIN DES MODIFICATIONS 👆

    montant_lettres = forms.CharField(
        label="Montant en lettres",
        required=False,
        widget=forms.Textarea(attrs={'rows': 2}),
        help_text="Rempli automatiquement selon les décomptes choisis.",
    )
    modalite_reglement = forms.ChoiceField(
        label="Modalité de règlement",
        required=False,
        choices=[('', 'Sélectionner un mode de règlement...')] + list(OrdrePaiement.MODALITES_CHOICES),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        reserved_ids = PeriodePaiement.objects.filter(
            reservation_active=True
        ).values_list('decompte_id', flat=True)
        
        qs = (
            Decompte.objects.filter(statut=Decompte.STATUT_VALIDE)
            .exclude(pk__in=reserved_ids)
            .select_related('agent')
            .order_by('-annee', '-mois')
        )
        self.fields['decomptes'].queryset = qs

        self.fields['decomptes'].label_from_instance = lambda obj: (
            f"{obj.agent.matricule} - {obj.agent.nom} | {obj.mois:02d}/{obj.annee} — {obj.montant_total:,.0f} Ar".replace(",", " ")
        )
        
        _apply_css(self)

    # 👇 SÉCURITÉ ANTI-DOUBLON 👇
    def clean_numero_op(self):
        numero_op = self.cleaned_data.get('numero_op')
        if OrdrePaiement.objects.filter(numero_op=numero_op).exists():
            raise forms.ValidationError("Ce numéro d'OP existe déjà. Veuillez en choisir un autre.")
        return numero_op

    def clean(self):
        cleaned = super().clean()
        agent = cleaned.get('agent')
        decomptes = cleaned.get('decomptes')

        # Cohérence agent ↔ décomptes
        if agent and decomptes:
            for d in decomptes:
                if d.agent_id != agent.pk:
                    self.add_error(
                        'decomptes',
                        f"Le décompte {d.annee}/{d.mois:02d} "
                        f"appartient à un autre agent."
                    )

        # Contrôle de présence de montant_lettres
        montant_total = Decimal('0.00')
        if decomptes:
            montant_total = sum(
                (d.montant_total for d in decomptes), Decimal('0.00')
            )
        montant_lettres = (cleaned.get('montant_lettres') or '').strip()
        if montant_total > 0 and not montant_lettres:
            self.add_error(
                'montant_lettres',
                "Le montant en lettres est obligatoire lorsque le montant "
                "total est positif."
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
