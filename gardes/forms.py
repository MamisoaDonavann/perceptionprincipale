"""
Formulaires de l'application gardes.

Important : la création d'une Garde passe par le service
`gardes.services.creer_garde()`, pas par un ModelForm.save() direct.
Le formulaire collecte donc uniquement les champs d'entrée.
"""

from django import forms

from agents.models import Agent
from missions.models import Mission
from tarifs.models import Tarif

from .models import Garde


class GardeForm(forms.Form):
    """
    Formulaire de saisie d'une garde.

    Le champ `tarif` est facultatif : s'il est vide, le service
    `creer_garde` sélectionne automatiquement le tarif applicable
    à la date de début de la garde.
    """

    agent = forms.ModelChoiceField(
        queryset=Agent.objects.filter(actif=True),
        label="Agent",
        required=True,
    )
    mission = forms.ModelChoiceField(
        queryset=Mission.objects.all(),
        label="Mission",
        required=False,
        help_text="Facultatif.",
    )
    tarif = forms.ModelChoiceField(
        queryset=Tarif.objects.filter(actif=True),
        label="Tarif applicable",
        required=False,
        help_text="Laisser vide pour sélection automatique selon la date.",
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
