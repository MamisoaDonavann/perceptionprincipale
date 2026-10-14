"""
Filtres de formatage pour les montants en Ariary.
"""

from decimal import Decimal, InvalidOperation

from django import template


register = template.Library()


@register.filter
def format_ar(value):
    """30000.00 → '30 000' (sans décimales si entier)."""
    try:
        d = Decimal(str(value))
        if d == d.to_integral_value():
            return f"{int(d):,}".replace(',', '\u202f')
        return f"{d:,.2f}".replace(',', '\u202f').replace('.', ',')
    except (InvalidOperation, TypeError, ValueError):
        return value


@register.filter
def format_ar_short(value):
    """Formatage compact pour graphiques : 1 500 000 → '1,5 M'."""
    try:
        d = Decimal(str(value))
        if d >= 1_000_000:
            return f"{d / 1_000_000:.1f} M".replace('.', ',')
        if d >= 1_000:
            return f"{d / 1_000:.0f} k"
        return f"{int(d)}"
    except (InvalidOperation, TypeError, ValueError):
        return value
