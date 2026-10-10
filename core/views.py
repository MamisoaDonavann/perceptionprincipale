"""
Vues de l'application core.

Contient la vue du tableau de bord (page d'accueil protégée).
"""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def dashboard(request):
    """
    Tableau de bord principal.

    Affiche des statistiques calculées à partir des données réelles
    de la base. Aucune donnée fictive.
    """
    from agents.models import Agent
    from missions.models import Mission
    from gardes.models import Garde
    from decomptes.models import Decompte
    from paiements.models import OrdrePaiement, Paiement

    stats = {
        'agents_actifs': Agent.objects.filter(actif=True).count(),
        'missions': Mission.objects.count(),
        'gardes_validees': Garde.objects.filter(
            statut=Garde.STATUT_VALIDEE
        ).count(),
        'decomptes_valides': Decompte.objects.filter(
            statut=Decompte.STATUT_VALIDE
        ).count(),
        'ordres_en_cours': OrdrePaiement.objects.filter(
            statut__in=[
                OrdrePaiement.STATUT_BROUILLON,
                OrdrePaiement.STATUT_VALIDE,
            ]
        ).count(),
        'ordres_payes': OrdrePaiement.objects.filter(
            statut=OrdrePaiement.STATUT_PAYE
        ).count(),
        'paiements_enregistres': Paiement.objects.filter(
            statut=Paiement.STATUT_ENREGISTRE
        ).count(),
    }
    stats['total_donnees'] = (
        stats['agents_actifs']
        + stats['missions']
        + stats['gardes_validees']
        + stats['decomptes_valides']
        + stats['ordres_en_cours']
        + stats['ordres_payes']
        + stats['paiements_enregistres']
    )

    return render(request, 'dashboard.html', {'stats': stats})
