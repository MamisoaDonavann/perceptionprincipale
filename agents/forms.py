"""
Formulaires de l'application agents.
"""

from django import forms

from .models import Agent


class AgentForm(forms.ModelForm):
    """
    Formulaire de création / modification d'un Agent.

    Utilise le widget DateInput pour la date de naissance.
    """

    class Meta:
        model = Agent
        fields = [
            'matricule', 'nom', 'prenoms', 'cin',
            'date_naissance', 'lieu_naissance', 'sexe', 'telephone',
            'grade', 'adresse', 'statut_agent', 'actif', 'observation',
        ]
        widgets = {
            'date_naissance': forms.DateInput(
                attrs={'type': 'date'}, format='%Y-%m-%d'
            ),
            'observation': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['date_naissance'].input_formats = ['%Y-%m-%d']
        for field in self.fields.values():
            css = 'form-input'
            if isinstance(field.widget, forms.Select):
                css = 'form-select'
            elif isinstance(field.widget, forms.Textarea):
                css = 'form-textarea'
            elif isinstance(field.widget, forms.CheckboxInput):
                css = 'form-checkbox'
            field.widget.attrs.setdefault('class', css)
