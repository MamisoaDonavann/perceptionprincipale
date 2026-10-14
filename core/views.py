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


# ===================================================================
# Recherche globale
# ===================================================================

@login_required
def global_search(request):
    """
    Recherche transverse dans les principales entités visibles par l'utilisateur.
    Chaque section est filtrée par les permissions correspondantes.
    """
    from django.db.models import Q

    q = request.GET.get('q', '').strip()
    results = {
        'q': q,
        'agents': [],
        'missions': [],
        'gardes': [],
        'decomptes': [],
        'ordres_paiement': [],
        'total': 0,
    }

    if q and len(q) >= 2:
        # -------- Agents --------
        if request.user.has_perm('agents.view_agent'):
            from agents.models import Agent
            results['agents'] = list(
                Agent.objects.filter(
                    Q(matricule__icontains=q)
                    | Q(nom__icontains=q)
                    | Q(prenoms__icontains=q)
                    | Q(cin__icontains=q)
                ).order_by('nom', 'prenoms')[:10]
            )

        # -------- Missions --------
        if request.user.has_perm('missions.view_mission'):
            from missions.models import Mission
            results['missions'] = list(
                Mission.objects.filter(
                    Q(numero_officiel__icontains=q)
                    | Q(libelle__icontains=q)
                    | Q(lieu__icontains=q)
                ).order_by('-date_debut')[:10]
            )

        # -------- Gardes (via agent) --------
        if request.user.has_perm('gardes.view_garde'):
            from gardes.models import Garde
            results['gardes'] = list(
                Garde.objects.filter(
                    Q(agent__matricule__icontains=q)
                    | Q(agent__nom__icontains=q)
                    | Q(agent__prenoms__icontains=q)
                ).select_related('agent').order_by('-date_heure_debut')[:10]
            )

        # -------- Décomptes (via agent) --------
        if request.user.has_perm('decomptes.view_decompte'):
            from decomptes.models import Decompte
            results['decomptes'] = list(
                Decompte.objects.filter(
                    Q(agent__matricule__icontains=q)
                    | Q(agent__nom__icontains=q)
                    | Q(agent__prenoms__icontains=q)
                ).select_related('agent').order_by('-annee', '-mois')[:10]
            )

        # -------- Ordres de paiement --------
        if request.user.has_perm('paiements.consulter_ordre_paiement'):
            from paiements.models import OrdrePaiement
            results['ordres_paiement'] = list(
                OrdrePaiement.objects.filter(
                    Q(numero_op__icontains=q)
                    | Q(agent_beneficiaire__matricule__icontains=q)
                    | Q(agent_beneficiaire__nom__icontains=q)
                    | Q(agent_beneficiaire__prenoms__icontains=q)
                ).select_related('agent_beneficiaire').order_by('-annee', '-numero_op')[:10]
            )

        results['total'] = (
            len(results['agents'])
            + len(results['missions'])
            + len(results['gardes'])
            + len(results['decomptes'])
            + len(results['ordres_paiement'])
        )

    return render(request, 'core/search_results.html', results)
