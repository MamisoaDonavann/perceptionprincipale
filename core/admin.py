from django.contrib import admin
from .models import Unite, Parametre


@admin.register(Unite)
class UniteAdmin(admin.ModelAdmin):
    list_display = ('code', 'libelle', 'actif', 'date_creation')
    list_filter = ('actif',)
    search_fields = ('code', 'libelle')
    ordering = ('code',)


@admin.register(Parametre)
class ParametreAdmin(admin.ModelAdmin):
    list_display = ('cle', 'valeur', 'date_maj', 'id_utilisateur_maj')
    search_fields = ('cle', 'description')
    ordering = ('cle',)
