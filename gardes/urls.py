"""
Routes de l'application gardes.
"""

from django.urls import path

from . import views


app_name = 'gardes'

urlpatterns = [
    path('', views.garde_list, name='list'),
    path('nouvelle/', views.garde_create, name='create'),
    path('<int:pk>/', views.garde_detail, name='detail'),
    path('<int:pk>/annuler/', views.garde_annuler, name='annuler'),
]
