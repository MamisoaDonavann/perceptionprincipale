from django.urls import path
from . import views

app_name = 'paiements'

urlpatterns = [
    path('', views.op_list, name='list'),
    path('nouveau/', views.op_create, name='create'),
    path('<int:pk>/', views.op_detail, name='detail'),
    path('<int:pk>/pdf-officiel/', views.op_pdf_officiel, name='op_pdf_officiel'),
    path('<int:pk>/excel-officiel/', views.op_excel_officiel, name='op_excel_officiel'),
    
    # 👇 NOUVELLE ROUTE POUR L'EXPORT GROUPÉ 👇
    path('export-etats-decomptes/', views.op_excel_etat_decompte_bulk, name='excel_etat_decompte_bulk'),
    
    path('<int:pk>/valider/', views.op_valider, name='valider'),
    path('<int:pk>/retirer-periode/', views.op_retirer_periode, name='retirer_periode'),
    path('<int:pk>/annuler/', views.op_annuler, name='annuler'),
    path('<int:pk>/cloturer/', views.op_cloturer, name='cloturer'),
    path('<int:pk>/paiement/nouveau/', views.paiement_create, name='paiement_create'),
    path('<int:pk>/paiement/<int:paiement_pk>/annuler/', views.paiement_annuler, name='paiement_annuler'),
    path('<int:pk>/paiement/<int:paiement_pk>/confirmer/', views.confirmation_create, name='confirmation_create'),
    path('<int:pk>/paiement/<int:paiement_pk>/confirmation/<int:confirmation_pk>/annuler/', views.confirmation_annuler, name='confirmation_annuler'),
]
