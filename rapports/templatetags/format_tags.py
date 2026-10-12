"""
Filtres de formatage pour les templates de rapports.

- format_ar      : montant Ariary avec espaces (ex. 30 000)
- format_ar_dec  : montant Ariary avec décimales si nécessaire
- format_datetime: JJ/MM/AAAA HH:MM:SS
- nom_mois       : numéro de mois → nom en français
"""

from decimal import Decimal, InvalidOperation

from django import template


register = template.Library()


MOIS_FR = {
    1: 'Janvier', 2: 'Février', 3: 'Mars', 4: 'Avril',
    5: 'Mai', 6: 'Juin', 7: 'Juillet', 8: 'Août',
    9: 'Septembre', 10: 'Octobre', 11: 'Novembre', 12: 'Décembre',
}


@register.filter
def format_ar(value):
    """30000.00 → '30 000' (sans décimales si entier)."""
    try:
        d = Decimal(str(value))
        if d == d.to_integral_value():
            return f"{int(d):,}".replace(',', '\u202f')  # espace fine insécable
        return f"{d:,.2f}".replace(',', '\u202f').replace('.', ',')
    except (InvalidOperation, TypeError, ValueError):
        return value


@register.filter
def format_ar_dec(value):
    """30000 → '30 000,00' (toujours 2 décimales)."""
    try:
        d = Decimal(str(value))
        return f"{d:,.2f}".replace(',', '\u202f').replace('.', ',')
    except (InvalidOperation, TypeError, ValueError):
        return value


@register.filter
def nom_mois(numero):
    """1 → 'Janvier'."""
    try:
        return MOIS_FR.get(int(numero), '')
    except (TypeError, ValueError):
        return ''
