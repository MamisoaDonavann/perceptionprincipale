"""
Routes de l'application rapports.
"""

from django.urls import path

from . import views


app_name = 'rapports'

urlpatterns = [
    path('', views.index, name='index'),

    # ------------------------------------------------------------------
    # Rapport 1 — État de décompte
    # ------------------------------------------------------------------
    path(
        'decompte/<int:pk>/pdf/',
        views.etat_decompte_pdf,
        name='etat_decompte_pdf',
    ),

    # ------------------------------------------------------------------
    # Récapitulatif mensuel (tous agents d'un mois)
    # ------------------------------------------------------------------
    path(
        'decomptes-mensuels/',
        views.filtres_decomptes_mensuels,
        name='filtres_decomptes_mensuels',
    ),
    path(
        'decomptes-mensuels/<int:annee>/<int:mois>/pdf/',
        views.decomptes_mensuels_pdf,
        name='decomptes_mensuels_pdf',
    ),

    # ------------------------------------------------------------------
    # Rapport 2 — Liste de paiement
    # ------------------------------------------------------------------
    path(
        'op/<int:pk>/pdf/',
        views.liste_paiement_pdf,
        name='liste_paiement_pdf',
    ),

    # ------------------------------------------------------------------
    # Rapport 3 — Historique agent
    # ------------------------------------------------------------------
    path(
        'agent/<int:pk>/pdf/',
        views.historique_agent_pdf,
        name='historique_agent_pdf',
    ),
    path(
        'agent/<int:pk>/excel/',
        views.historique_agent_excel,
        name='historique_agent_excel',
    ),

    # ------------------------------------------------------------------
    # Rapport 4 — État détaillé des gardes
    # ------------------------------------------------------------------
    path(
        'gardes/',
        views.filtres_gardes,
        name='filtres_gardes',
    ),
    path(
        'gardes/pdf/',
        views.etat_gardes_pdf,
        name='etat_gardes_pdf',
    ),
    path(
        'gardes/excel/',
        views.etat_gardes_excel,
        name='etat_gardes_excel',
    ),

    # ------------------------------------------------------------------
    # Rapport 5 — Liste des OP
    # ------------------------------------------------------------------
    path(
        'liste-op/',
        views.filtres_op,
        name='filtres_op',
    ),
    path(
        'liste-op/pdf/',
        views.liste_op_pdf,
        name='liste_op_pdf',
    ),
    path(
        'liste-op/excel/',
        views.liste_op_excel,
        name='liste_op_excel',
    ),

    # ------------------------------------------------------------------
    # Rapport 6 — Rapport mensuel
    # ------------------------------------------------------------------
    path(
        'mensuel/<int:annee>/<int:mois>/pdf/',
        views.rapport_mensuel_pdf,
        name='rapport_mensuel_pdf',
    ),

    # ------------------------------------------------------------------
    # Rapport 7 — Rapport sur période
    # ------------------------------------------------------------------
    path(
        'periode/',
        views.filtres_periode,
        name='filtres_periode',
    ),
    path(
        'periode/pdf/',
        views.rapport_periode_pdf,
        name='rapport_periode_pdf',
    ),
    path(
        'periode/excel/',
        views.rapport_periode_excel,
        name='rapport_periode_excel',
    ),
]
