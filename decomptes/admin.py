from django.contrib import admin

from .models import Decompte, LigneDecompte


class LigneDecompteInline(admin.TabularInline):
    model = LigneDecompte
    extra = 0
    can_delete = False
    readonly_fields = (
        'garde', 'tarif',
        'duree_minutes_snapshot',
        'nombre_partiels_snapshot',
        'montant_partiel_snapshot',
        'montant_ligne',
    )

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Decompte)
class DecompteAdmin(admin.ModelAdmin):
    list_display = (
        'agent', 'annee', 'mois', 'statut',
        'montant_total', 'nombre_gardes_retunes',
        'nombre_gardes_non_conformes_exclues',
        'id_utilisateur_createur', 'date_creation',
        'id_utilisateur_validateur', 'date_validation',
    )
    list_filter = ('statut', 'annee', 'mois', 'agent')
    search_fields = ('agent__matricule', 'agent__nom', 'agent__prenoms')
    ordering = ('-annee', '-mois')
    date_hierarchy = 'date_creation'
    readonly_fields = (
        'agent', 'annee', 'mois', 'statut',
        'montant_total', 'nombre_gardes_retunes',
        'nombre_gardes_non_conformes_exclues',
        'id_utilisateur_createur', 'date_creation',
        'id_utilisateur_validateur', 'date_validation',
    )
    inlines = [LigneDecompteInline]
    autocomplete_fields = ('agent', 'id_utilisateur_createur', 'id_utilisateur_validateur')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        # Lecture seule complète : la validation passe par le service.
        return False

    def has_delete_permission(self, request, obj=None):
        return False
