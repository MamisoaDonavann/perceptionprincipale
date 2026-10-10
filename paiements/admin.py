from django.contrib import admin

from .models import (
    CompteurOP, OrdrePaiement, PeriodePaiement,
    Paiement, ConfirmationReception,
)


class PeriodePaiementInline(admin.TabularInline):
    model = PeriodePaiement
    extra = 0
    can_delete = False
    readonly_fields = ('decompte', 'montant_source', 'reservation_active', 'date_ajout')
    def has_add_permission(self, request, obj=None): return False


class PaiementInline(admin.TabularInline):
    model = Paiement
    extra = 0
    can_delete = False
    readonly_fields = (
        'montant', 'date_paiement', 'mode_paiement', 'reference',
        'statut', 'id_utilisateur_enregistreur', 'date_enregistrement',
        'motif_annulation', 'id_utilisateur_annulateur', 'date_annulation',
    )
    def has_add_permission(self, request, obj=None): return False


class ConfirmationInline(admin.TabularInline):
    model = ConfirmationReception
    extra = 0
    can_delete = False
    readonly_fields = (
        'date_confirmation', 'id_utilisateur_confirmation', 'mode',
        'justificatif', 'statut', 'motif_annulation',
        'id_utilisateur_annulateur', 'date_annulation',
    )
    def has_add_permission(self, request, obj=None): return False


@admin.register(CompteurOP)
class CompteurOPAdmin(admin.ModelAdmin):
    list_display = ('annee', 'dernier_numero')
    ordering = ('-annee',)


@admin.register(OrdrePaiement)
class OrdrePaiementAdmin(admin.ModelAdmin):
    list_display = (
        'numero_op', 'agent_beneficiaire', 'annee', 'statut',
        'montant_total', 'montant_net_paye', 'cloture_administrative',
        'id_utilisateur_createur', 'date_creation',
    )
    list_filter = ('statut', 'annee', 'cloture_administrative', 'agent_beneficiaire')
    search_fields = ('numero_op', 'agent_beneficiaire__matricule', 'agent_beneficiaire__nom')
    ordering = ('-annee', '-numero_op')
    date_hierarchy = 'date_creation'
    readonly_fields = (
        'numero_op', 'annee', 'statut', 'montant_total', 'montant_net_paye',
        'id_utilisateur_createur', 'date_creation',
        'id_utilisateur_validateur', 'date_validation',
        'cloture_administrative', 'date_cloture', 'id_utilisateur_cloture',
        'motif_annulation',
    )
    inlines = [PeriodePaiementInline, PaiementInline]
    autocomplete_fields = ('agent_beneficiaire',)

    def has_add_permission(self, request): return False
    def has_delete_permission(self, request, obj=None): return False


@admin.register(Paiement)
class PaiementAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'ordre_paiement', 'montant', 'mode_paiement',
        'statut', 'date_paiement', 'id_utilisateur_enregistreur',
    )
    list_filter = ('statut', 'mode_paiement', 'date_paiement')
    search_fields = ('ordre_paiement__numero_op', 'reference')
    ordering = ('-date_paiement',)
    readonly_fields = (
        'ordre_paiement', 'montant', 'date_paiement', 'mode_paiement',
        'reference', 'statut', 'motif_annulation',
        'id_utilisateur_enregistreur', 'date_enregistrement',
        'id_utilisateur_annulateur', 'date_annulation',
    )
    inlines = [ConfirmationInline]   # ← déplacé ici, sur Paiement
    def has_add_permission(self, request): return False
    def has_delete_permission(self, request, obj=None): return False


@admin.register(ConfirmationReception)
class ConfirmationReceptionAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'paiement', 'date_confirmation',
        'id_utilisateur_confirmation', 'mode', 'statut',
    )
    list_filter = ('statut', 'mode', 'date_confirmation')
    search_fields = ('paiement__ordre_paiement__numero_op',)
    ordering = ('-date_confirmation',)
    readonly_fields = (
        'paiement', 'date_confirmation', 'id_utilisateur_confirmation',
        'mode', 'justificatif', 'statut', 'motif_annulation',
        'id_utilisateur_annulateur', 'date_annulation',
    )
    def has_add_permission(self, request): return False
    def has_delete_permission(self, request, obj=None): return False
