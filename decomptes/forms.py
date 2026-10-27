"""
Formulaires de l'application decomptes.
"""

from datetime import date

from django import forms

from agents.models import Agent


MOIS_CHOICES = [
    (1, 'Janvier'), (2, 'Février'), (3, 'Mars'), (4, 'Avril'),
    (5, 'Mai'), (6, 'Juin'), (7, 'Juillet'), (8, 'Août'),
    (9, 'Septembre'), (10, 'Octobre'), (11, 'Novembre'), (12, 'Décembre'),
]


class DecompteForm(forms.Form):
    """
    Formulaire de création d'un décompte mensuel.
    """

    agent = forms.ModelChoiceField(
        queryset=Agent.objects.filter(actif=True),
        label="Agent",
        required=True,
        empty_label="Sélectionner un agent...", # 👈 AJOUTÉ ICI
    )
    annee = forms.IntegerField(
        label="Année",
        min_value=1900,
        max_value=2200,
        initial=date.today().year,
    )
    mois = forms.TypedChoiceField(
        label="Mois",
        choices=MOIS_CHOICES,
        coerce=int,
        initial=date.today().month,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css = 'form-input'
            if isinstance(field.widget, forms.Select):
                css = 'form-select'
            field.widget.attrs.setdefault('class', css)
