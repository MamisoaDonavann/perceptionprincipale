"""
Routes de l'application decomptes.
"""

from django.urls import path

from . import views


app_name = 'decomptes'

urlpatterns = [
    path('', views.decompte_list, name='list'),
    path('nouveau/', views.decompte_create, name='create'),
    path('<int:pk>/', views.decompte_detail, name='detail'),
    path('<int:pk>/valider/', views.decompte_valider, name='valider'),
]
