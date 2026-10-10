"""
Routes de l'application agents.
"""

from django.urls import path

from . import views


app_name = 'agents'

urlpatterns = [
    path('', views.agent_list, name='list'),
    path('nouveau/', views.agent_create, name='create'),
    path('<int:pk>/', views.agent_detail, name='detail'),
    path('<int:pk>/modifier/', views.agent_update, name='update'),
]
