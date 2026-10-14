"""
Routes de l'application core.
"""

from django.urls import path

from .views import dashboard, global_search


urlpatterns = [
    path('', dashboard, name='dashboard'),
    path('recherche/', global_search, name='search'),
]
