"""
Contrôle d'accès aux rapports.

Chaque rapport exige une permission métier spécifique.
"""

from django.core.exceptions import PermissionDenied


def verifier_permission(user, permission):
    """
    Lève PermissionDenied si l'utilisateur n'a pas la permission.

    Paramètre `permission` : chaîne au format 'app_label.codename'.
    """
    if not user.has_perm(permission):
        raise PermissionDenied(
            f"Permission requise pour ce rapport : {permission}."
        )
