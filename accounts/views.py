"""
Vues d'authentification de l'application accounts.

Utilise les vues natives Django LoginView et LogoutView, avec
personnalisation des templates.
"""

from django.contrib.auth.views import LoginView, LogoutView
from django.urls import reverse_lazy


class CustomLoginView(LoginView):
    """Vue de connexion avec template personnalisé."""
    template_name = 'registration/login.html'
    redirect_authenticated_user = True


class CustomLogoutView(LogoutView):
    """
    Vue de déconnexion par POST uniquement (Django 5.x).
    Redirige vers la page 'logged_out'.
    """
    next_page = reverse_lazy('logged_out')
