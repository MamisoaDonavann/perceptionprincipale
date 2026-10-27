"""
Formulaires de l'application gardes.
"""

from django import forms

from agents.models import Agent
from missions.models import Mission
from tarifs.models import Tarif

from .models import Garde


class GardeForm(forms.Form):
    """
    Formulaire de saisie d'une garde.
    """

    agent = forms.ModelChoiceField(
        queryset=Agent.objects.filter(actif=True),
        label="Agent",
        required=True,
        empty_label="Sélectionner un agent...", # 👈 MODIFIÉ ICI
    )
    mission = forms.ModelChoiceField(
        queryset=Mission.objects.all(),
        label="Mission",
        required=False,
        help_text="Facultatif.",
        empty_label="Sélectionner une mission...", # 👈 MODIFIÉ ICI
    )
    tarif = forms.ModelChoiceField(
        queryset=Tarif.objects.filter(actif=True),
        label="Tarif applicable",
        required=False,
        help_text="Laisser vide pour sélection automatique selon la date.",
        empty_label="Sélectionner un tarif...", # 👈 MODIFIÉ ICI
    )
    date_heure_debut = forms.DateTimeField(
        label="Date et heure de début",
        input_formats=['%Y-%m-%dT%H:%M'],
        widget=forms.DateTimeInput(
            attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'
        ),
    )
    date_heure_fin = forms.DateTimeField(
        label="Date et heure de fin",
        input_formats=['%Y-%m-%dT%H:%M'],
        widget=forms.DateTimeInput(
            attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'
        ),
    )
    observation = forms.CharField(
        label="Observation",
        required=False,
        widget=forms.Textarea(attrs={'rows': 3}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            css = 'form-input'
            if isinstance(field.widget, forms.Select):
                css = 'form-select'
            elif isinstance(field.widget, forms.Textarea):
                css = 'form-textarea'
            field.widget.attrs.setdefault('class', css)

    def clean(self):
        cleaned = super().clean()
        debut = cleaned.get('date_heure_debut')
        fin = cleaned.get('date_heure_fin')
        if debut and fin:
            if fin <= debut:
                self.add_error(
                    'date_heure_fin',
                    "La fin doit être strictement postérieure au début."
                )
        return cleaned


class AnnulationGardeForm(forms.Form):
    """Formulaire d'annulation d'une garde."""

    motif = forms.CharField(
        label="Motif d'annulation",
        required=True,
        widget=forms.Textarea(attrs={'rows': 3, 'class': 'form-textarea'}),
    )
