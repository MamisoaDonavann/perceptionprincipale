"""
Routes de l'application missions.
"""

from django.urls import path

from . import views


app_name = 'missions'

urlpatterns = [
    path('', views.mission_list, name='list'),
    path('nouvelle/', views.mission_create, name='create'),
    path('<int:pk>/', views.mission_detail, name='detail'),
    path('<int:pk>/modifier/', views.mission_update, name='update'),
    path('<int:pk>/participants/ajouter/', views.participation_create, name='participation_create'),
    path('<int:pk>/participants/<int:participation_pk>/retirer/', views.participation_delete, name='participation_delete'),
]
