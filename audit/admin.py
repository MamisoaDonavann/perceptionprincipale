from django.contrib import admin

from .models import JournalAudit


@admin.register(JournalAudit)
class JournalAuditAdmin(admin.ModelAdmin):
    """
    Admin du journal d'audit.

    Lecture seule : aucune création, modification ou suppression
    n'est autorisée via l'admin. Seule la consultation est permise.
    """

    list_display = (
        'date_action',
        'id_utilisateur',
        'action',
        'entite_concernee',
        'id_entite_concernee',
    )
    list_filter = ('action', 'entite_concernee', 'date_action')
    search_fields = (
        'id_utilisateur__username',
        'entite_concernee',
        'commentaire',
    )
    ordering = ('-date_action',)
    date_hierarchy = 'date_action'
    readonly_fields = (
        'id_utilisateur',
        'action',
        'entite_concernee',
        'id_entite_concernee',
        'date_action',
        'valeurs_avant',
        'valeurs_apres',
        'commentaire',
        'adresse_ip',
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
