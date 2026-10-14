"""
Vues de l'application core.

Contient la vue du tableau de bord (page d'accueil protégée) et
la recherche globale.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum
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
    from audit.models import JournalAudit

    # ---------------- Statistiques principales ----------------
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

    # ---------------- Montants clés ----------------
    today = date.today()
    debut_annee = date(today.year, 1, 1)

    # Reste à payer : OP VALIDE dont net < total
    op_valides = OrdrePaiement.objects.filter(
        statut=OrdrePaiement.STATUT_VALIDE
    )
    reste_a_payer = sum(
        (op.montant_total - op.montant_net_paye for op in op_valides),
        Decimal('0.00')
    )

    # Total payé cette année
    total_paye_annee = Paiement.objects.filter(
        statut=Paiement.STATUT_ENREGISTRE,
        date_paiement__year=today.year,
    ).aggregate(s=Sum('montant'))['s'] or Decimal('0.00')

    # Total décomptes validés cette année
    total_decomptes_annee = Decompte.objects.filter(
        statut=Decompte.STATUT_VALIDE,
        annee=today.year,
    ).aggregate(s=Sum('montant_total'))['s'] or Decimal('0.00')

    montants = {
        'reste_a_payer': reste_a_payer,
        'total_paye_annee': total_paye_annee,
        'total_decomptes_annee': total_decomptes_annee,
    }

    # ---------------- Activité récente ----------------
    activite = JournalAudit.objects.select_related('id_utilisateur').order_by('-date_action')[:10]

    # ---------------- Évolution mensuelle des paiements (12 mois) ----------------
    # Récupère les paiements des 12 derniers mois
    douze_mois = []
    for i in range(11, -1, -1):
        # Remonte de 11 mois
        mois_courant = today.month - i
        annee_courante = today.year
        while mois_courant <= 0:
            mois_courant += 12
            annee_courante -= 1
        total = Paiement.objects.filter(
            statut=Paiement.STATUT_ENREGISTRE,
            date_paiement__year=annee_courante,
            date_paiement__month=mois_courant,
        ).aggregate(s=Sum('montant'))['s'] or Decimal('0.00')
        douze_mois.append({
            'annee': annee_courante,
            'mois': mois_courant,
            'total': total,
        })

    # Calcule la hauteur relative des barres (pour le graphique CSS)
    max_montant = max((m['total'] for m in douze_mois), default=Decimal('0.00'))
    if max_montant > 0:
        for m in douze_mois:
            m['hauteur_pct'] = float(m['total']) / float(max_montant) * 100
    else:
        for m in douze_mois:
            m['hauteur_pct'] = 0

    # ---------------- Permissions pour raccourcis ----------------
    permissions = {
        'creer_agent': request.user.has_perm('agents.add_agent'),
        'creer_mission': request.user.has_perm('missions.add_mission'),
        'creer_garde': request.user.has_perm('gardes.add_garde'),
        'creer_decompte': request.user.has_perm('decomptes.add_decompte'),
        'creer_op': request.user.has_perm('paiements.creer_ordre_paiement'),
        'voir_rapports': request.user.has_perm('decomptes.view_decompte'),
        'voir_audit': request.user.has_perm('audit.view_journalaudit'),
    }

    return render(request, 'dashboard.html', {
        'stats': stats,
        'montants': montants,
        'activite': activite,
        'evolution_mensuelle': douze_mois,
        'permissions': permissions,
    })


# ===================================================================
# Recherche globale
# ===================================================================

@login_required
def global_search(request):
    """
    Recherche transverse dans les principales entités visibles par l'utilisateur.
    Chaque section est filtrée par les permissions correspondantes.
    """
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

        # -------- Gardes --------
        if request.user.has_perm('gardes.view_garde'):
            from gardes.models import Garde
            results['gardes'] = list(
                Garde.objects.filter(
                    Q(agent__matricule__icontains=q)
                    | Q(agent__nom__icontains=q)
                    | Q(agent__prenoms__icontains=q)
                ).select_related('agent').order_by('-date_heure_debut')[:10]
            )

        # -------- Décomptes --------
        if request.user.has_perm('decomptes.view_decompte'):
            from decomptes.models import Decompte
            results['decomptes'] = list(
                Decompte.objects.filter(
                    Q(agent__matricule__icontains=q)
                    | Q(agent__nom__icontains=q)
                    | Q(agent__prenoms__icontains=q)
                ).select_related('agent').order_by('-annee', '-mois')[:10]
            )

        # -------- OP --------
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
