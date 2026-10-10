"""
Routes de l'application rapports.
"""

from django.urls import path

from . import views


app_name = 'rapports'

urlpatterns = [
    path('', views.index, name='index'),
    path('decompte/<int:pk>/pdf/', views.etat_decompte_pdf, name='etat_decompte_pdf'),
    path('op/<int:pk>/pdf/', views.liste_paiement_pdf, name='liste_paiement_pdf'),
    path('agent/<int:pk>/pdf/', views.historique_agent_pdf, name='historique_agent_pdf'),
    path('agent/<int:pk>/excel/', views.historique_agent_excel, name='historique_agent_excel'),
]
