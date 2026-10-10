from django.contrib import admin

from .models import Garde


@admin.register(Garde)
class GardeAdmin(admin.ModelAdmin):
    list_display = (
        'agent',
        'date_heure_debut',
        'date_heure_fin',
        'duree_minutes',
        'nombre_partiels',
        'conforme',
        'tarif',
        'statut',
    )
    list_filter = ('statut', 'conforme', 'tarif', 'agent')
    search_fields = (
        'agent__matricule',
        'agent__nom',
        'agent__prenoms',
        'mission__numero_officiel',
        'mission__libelle',
    )
    ordering = ('-date_heure_debut',)
    date_hierarchy = 'date_heure_debut'
    readonly_fields = (
        'duree_minutes',
        'nombre_partiels',
        'conforme',
        'motif_anomalie',
        'date_saisie',
        'date_maj',
    )
    autocomplete_fields = ('agent', 'mission', 'tarif', 'id_utilisateur_saisie')
    fieldsets = (
        ("Agent et mission", {
            'fields': ('agent', 'mission')
        }),
        ("Période", {
            'fields': ('date_heure_debut', 'date_heure_fin')
        }),
        ("Calculs (lecture seule)", {
            'fields': (
                'duree_minutes',
                'nombre_partiels',
                'conforme',
                'motif_anomalie',
            ),
            'description': (
                "Les champs de calcul sont générés automatiquement "
                "et ne peuvent pas être modifiés manuellement."
            )
        }),
        ("Tarif", {
            'fields': ('tarif',),
            'description': (
                "Le tarif doit être applicable à la date de début "
                "de la garde."
            )
        }),
        ("Statut et observation", {
            'fields': ('statut', 'observation')
        }),
        ("Traçabilité", {
            'fields': ('id_utilisateur_saisie', 'date_saisie', 'date_maj'),
            'classes': ('collapse',)
        }),
    )
