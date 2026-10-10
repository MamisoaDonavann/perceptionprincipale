"""
Routes de l'application audit.
"""

from django.urls import path

from . import views


app_name = 'audit'

urlpatterns = [
    path('', views.journal_list, name='list'),
    path('<int:pk>/', views.journal_detail, name='detail'),
]
