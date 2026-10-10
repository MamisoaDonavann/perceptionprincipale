from django.contrib import admin

from .models import Mission, ParticipationMission


@admin.register(Mission)
class MissionAdmin(admin.ModelAdmin):
    list_display = (
        'numero_officiel',
        'libelle',
        'lieu',
        'date_debut',
        'date_fin',
        'statut',
    )
    list_filter = ('statut', 'date_debut')
    search_fields = ('numero_officiel', 'libelle', 'lieu')
    ordering = ('-date_debut',)
    readonly_fields = ('date_creation', 'date_maj')
    date_hierarchy = 'date_debut'
    fieldsets = (
        ("Identification", {
            'fields': ('numero_officiel', 'libelle', 'description', 'lieu')
        }),
        ("Période", {
            'fields': ('date_debut', 'date_fin')
        }),
        ("Statut (PROVISOIRE)", {
            'fields': ('statut',),
            'description': "Les statuts sont provisoires et à valider."
        }),
        ("Divers", {
            'fields': ('observation',)
        }),
        ("Traçabilité", {
            'fields': ('date_creation', 'date_maj'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ParticipationMission)
class ParticipationMissionAdmin(admin.ModelAdmin):
    list_display = (
        'mission',
        'agent',
        'date_debut_participation',
        'date_fin_participation',
    )
    list_filter = ('mission', 'date_debut_participation')
    search_fields = (
        'mission__numero_officiel',
        'mission__libelle',
        'agent__matricule',
        'agent__nom',
        'agent__prenoms',
    )
    ordering = ('mission', 'agent')
    readonly_fields = ('date_creation',)
    autocomplete_fields = ('mission', 'agent')
