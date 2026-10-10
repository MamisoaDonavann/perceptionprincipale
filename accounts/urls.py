"""
Routes de l'application accounts.
"""

from django.urls import path
from django.views.generic import TemplateView

from .views import CustomLoginView, CustomLogoutView


urlpatterns = [
    path('login/', CustomLoginView.as_view(), name='login'),
    path('logout/', CustomLogoutView.as_view(), name='logout'),
    path(
        'logged-out/',
        TemplateView.as_view(template_name='registration/logged_out.html'),
        name='logged_out',
    ),
]
