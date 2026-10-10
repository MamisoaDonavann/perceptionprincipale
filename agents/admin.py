from django.contrib import admin

from .models import Agent, AffectationAgent


@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    list_display = (
        'matricule',
        'nom',
        'prenoms',
        'grade',
        'statut_agent',
        'actif',
        'date_creation',
    )
    list_filter = ('statut_agent', 'actif', 'sexe')
    search_fields = ('matricule', 'nom', 'prenoms', 'cin', 'telephone')
    ordering = ('nom', 'prenoms')
    readonly_fields = ('date_creation', 'date_maj')
    fieldsets = (
        ("Identification", {
            'fields': ('matricule', 'nom', 'prenoms', 'cin')
        }),
        ("Informations personnelles", {
            'fields': ('date_naissance', 'lieu_naissance', 'sexe', 'telephone')
        }),
        ("Fonction", {
            'fields': ('grade',)
        }),
        ("Statut (PROVISOIRE)", {
            'fields': ('statut_agent', 'actif'),
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


@admin.register(AffectationAgent)
class AffectationAgentAdmin(admin.ModelAdmin):
    list_display = (
        'agent',
        'unite',
        'date_debut',
        'date_fin',
        'date_creation',
    )
    list_filter = ('unite', 'date_debut', 'date_fin')
    search_fields = (
        'agent__matricule',
        'agent__nom',
        'agent__prenoms',
        'unite__code',
        'unite__libelle',
    )
    ordering = ('agent', '-date_debut')
    readonly_fields = ('date_creation',)
    autocomplete_fields = ('agent', 'unite')
