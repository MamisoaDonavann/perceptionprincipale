"""
Formulaires de l'application missions.
"""

from django import forms

from agents.models import Agent

from .models import Mission, ParticipationMission


class MissionForm(forms.ModelForm):
    """Formulaire de création / modification d'une Mission."""

    class Meta:
        model = Mission
        fields = [
            'numero_officiel', 'libelle', 'description', 'lieu',
            'date_debut', 'date_fin', 'statut', 'observation',
        ]
        widgets = {
            'date_debut': forms.DateTimeInput(
                attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'
            ),
            'date_fin': forms.DateTimeInput(
                attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'
            ),
            'description': forms.Textarea(attrs={'rows': 3}),
            'observation': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['date_debut'].input_formats = ['%Y-%m-%dT%H:%M']
        self.fields['date_fin'].input_formats = ['%Y-%m-%dT%H:%M']
        for field in self.fields.values():
            css = 'form-input'
            if isinstance(field.widget, forms.Select):
                css = 'form-select'
            elif isinstance(field.widget, forms.Textarea):
                css = 'form-textarea'
            field.widget.attrs.setdefault('class', css)


class ParticipationMissionForm(forms.ModelForm):
    """
    Formulaire d'ajout d'un participant à une mission.

    Le champ `mission` est exclu : la mission est fournie par la vue.
    """

    class Meta:
        model = ParticipationMission
        fields = [
            'agent',
            'date_debut_participation',
            'date_fin_participation',
            'observation',
        ]
        widgets = {
            'date_debut_participation': forms.DateTimeInput(
                attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'
            ),
            'date_fin_participation': forms.DateTimeInput(
                attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'
            ),
            'observation': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, mission=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.mission = mission
        # Limiter aux agents actifs
        self.fields['agent'].queryset = Agent.objects.filter(actif=True)
        self.fields['date_debut_participation'].input_formats = ['%Y-%m-%dT%H:%M']
        self.fields['date_fin_participation'].input_formats = ['%Y-%m-%dT%H:%M']
        for field in self.fields.values():
            css = 'form-input'
            if isinstance(field.widget, forms.Select):
                css = 'form-select'
            elif isinstance(field.widget, forms.Textarea):
                css = 'form-textarea'
            field.widget.attrs.setdefault('class', css)

    def clean(self):
        cleaned = super().clean()
        if not self.mission:
            return cleaned
        debut = cleaned.get('date_debut_participation')
        fin = cleaned.get('date_fin_participation')
        if debut and fin and fin < debut:
            self.add_error(
                'date_fin_participation',
                "La date de fin doit être postérieure ou égale au début."
            )
        if debut and debut < self.mission.date_debut:
            self.add_error(
                'date_debut_participation',
                "La participation doit débuter après le début de la mission."
            )
        if fin and fin > self.mission.date_fin:
            self.add_error(
                'date_fin_participation',
                "La participation doit se terminer avant la fin de la mission."
            )
        return cleaned
