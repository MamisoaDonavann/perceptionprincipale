"""
Formulaires de l'application tarifs.
"""

from django import forms

from .models import Tarif


class TarifForm(forms.ModelForm):
    """
    Formulaire de création / modification d'un Tarif.

    Le champ id_utilisateur_createur n'est pas exposé : il est
    défini automatiquement à l'utilisateur connecté dans la vue.
    """

    class Meta:
        model = Tarif
        fields = [
            'montant_partiel',
            'date_debut_validite',
            'date_fin_validite',
            'actif',
            'motif_modification',
        ]
        widgets = {
            'date_debut_validite': forms.DateInput(
                attrs={'type': 'date'}, format='%Y-%m-%d'
            ),
            'date_fin_validite': forms.DateInput(
                attrs={'type': 'date'}, format='%Y-%m-%d'
            ),
            'motif_modification': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['date_debut_validite'].input_formats = ['%Y-%m-%d']
        self.fields['date_fin_validite'].input_formats = ['%Y-%m-%d']
        for field in self.fields.values():
            css = 'form-input'
            if isinstance(field.widget, forms.Select):
                css = 'form-select'
            elif isinstance(field.widget, forms.Textarea):
                css = 'form-textarea'
            elif isinstance(field.widget, forms.CheckboxInput):
                css = 'form-checkbox'
            field.widget.attrs.setdefault('class', css)

    def clean(self):
        cleaned = super().clean()
        debut = cleaned.get('date_debut_validite')
        fin = cleaned.get('date_fin_validite')
        if debut and fin and fin < debut:
            self.add_error(
                'date_fin_validite',
                "La date de fin doit être postérieure ou égale au début."
            )
        return cleaned
