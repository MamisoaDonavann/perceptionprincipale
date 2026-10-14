"""
Filtres de template pour les initiales et les couleurs d'avatars.
"""

from django import template

register = template.Library()

AVATAR_COLORS = ['c1', 'c2', 'c3', 'c4', 'c5', 'c6']


@register.filter
def initials(nom, prenoms=''):
    """
    Retourne les initiales à partir du nom et prénoms.
    Ex : 'Rakoto', 'Jean' → 'RJ'
    """
    first = str(nom or '').strip()[:1].upper()
    second = str(prenoms or '').strip()[:1].upper()
    result = first + second
    return result or '?'


@register.filter
def avatar_color(value):
    """
    Retourne une classe de couleur (c1..c6) basée sur un index.
    Peut prendre un entier ou une chaîne (on utilise un hash léger).
    """
    try:
        n = int(value)
    except (TypeError, ValueError):
        n = sum(ord(c) for c in str(value or ''))
    return 'avatar--' + AVATAR_COLORS[n % len(AVATAR_COLORS)]
