"""
Routes de l'application tarifs.
"""

from django.urls import path

from . import views


app_name = 'tarifs'

urlpatterns = [
    path('', views.tarif_list, name='list'),
    path('nouveau/', views.tarif_create, name='create'),
    path('<int:pk>/', views.tarif_detail, name='detail'),
    path('<int:pk>/modifier/', views.tarif_update, name='update'),
    path('<int:pk>/toggle-actif/', views.tarif_toggle_actif, name='toggle_actif'),
]
