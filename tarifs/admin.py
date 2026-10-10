from django.contrib import admin

from .models import Tarif


@admin.register(Tarif)
class TarifAdmin(admin.ModelAdmin):
    list_display = (
        'montant_partiel',
        'date_debut_validite',
        'date_fin_validite',
        'actif',
        'id_utilisateur_createur',
        'date_creation',
    )
    list_filter = ('actif', 'date_debut_validite', 'date_fin_validite')
    search_fields = ('motif_modification',)
    ordering = ('-date_debut_validite',)
    readonly_fields = ('date_creation',)
    date_hierarchy = 'date_debut_validite'
    autocomplete_fields = ('id_utilisateur_createur',)
    fieldsets = (
        ("Tarif", {
            'fields': ('montant_partiel',)
        }),
        ("Période de validité", {
            'fields': ('date_debut_validite', 'date_fin_validite')
        }),
        ("Activation", {
            'fields': ('actif',),
            'description': (
                "Désactiver un tarif erroné sans altérer son historique. "
                "Aucune suppression physique."
            )
        }),
        ("Traçabilité", {
            'fields': ('id_utilisateur_createur', 'date_creation', 'motif_modification')
        }),
    )
