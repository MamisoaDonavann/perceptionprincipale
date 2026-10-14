"""
Routes de l'application core.
"""

from django.urls import path

from . import views


app_name = 'core'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('recherche/', views.global_search, name='search'),
]
