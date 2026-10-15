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


def _mois_relatif(annee, mois, delta):
    """Retourne (annee, mois) décalé de `delta` mois."""
    m = mois + delta
    a = annee
    while m <= 0:
        m += 12
        a -= 1
    while m > 12:
        m -= 12
        a += 1
    return a, m


def _sparkline_paiements(nb_mois=6):
    """Retourne une liste de montants mensuels pour la sparkline."""
    today = date.today()
    valeurs = []
    for i in range(nb_mois - 1, -1, -1):
        a, m = _mois_relatif(today.year, today.month, -i)
        total = Paiement_total_mois(a, m)
        valeurs.append(float(total))
    return valeurs


def Paiement_total_mois(annee, mois):
    """Total des paiements enregistrés pour un mois donné."""
    from paiements.models import Paiement
    return Paiement.objects.filter(
        statut=Paiement.STATUT_ENREGISTRE,
        date_paiement__year=annee,
        date_paiement__month=mois,
    ).aggregate(s=Sum('montant'))['s'] or Decimal('0.00')


@login_required
def dashboard(request):
    """Tableau de bord principal. Statistiques calculées sur données réelles."""
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
        'gardes_validees': Garde.objects.filter(statut=Garde.STATUT_VALIDEE).count(),
        'decomptes_valides': Decompte.objects.filter(statut=Decompte.STATUT_VALIDE).count(),
        'ordres_en_cours': OrdrePaiement.objects.filter(
            statut__in=[OrdrePaiement.STATUT_BROUILLON, OrdrePaiement.STATUT_VALIDE]
        ).count(),
        'ordres_payes': OrdrePaiement.objects.filter(statut=OrdrePaiement.STATUT_PAYE).count(),
        'paiements_enregistres': Paiement.objects.filter(
            statut=Paiement.STATUT_ENREGISTRE
        ).count(),
    }
    stats['total_donnees'] = sum(stats.values())

    # ---------------- Montants clés + tendances ----------------
    today = date.today()

    # Reste à payer (OP validés)
    op_valides = OrdrePaiement.objects.filter(statut=OrdrePaiement.STATUT_VALIDE)
    reste_a_payer = sum(
        (op.montant_total - op.montant_net_paye for op in op_valides),
        Decimal('0.00')
    )

    # Total payé ce mois et mois précédent
    a_prec, m_prec = _mois_relatif(today.year, today.month, -1)
    total_paye_mois = Paiement_total_mois(today.year, today.month)
    total_paye_prec = Paiement_total_mois(a_prec, m_prec)

    def tendance(actuel, precedent):
        """Retourne (direction, pourcentage)."""
        if precedent == 0:
            if actuel == 0:
                return 'flat', 0
            return 'up', 100
        delta = (actuel - precedent) / precedent * 100
        if delta > 1:
            return 'up', round(delta)
        if delta < -1:
            return 'down', abs(round(delta))
        return 'flat', 0

    dir_paye, pct_paye = tendance(total_paye_mois, total_paye_prec)

    # Décomptes validés ce mois vs précédent
    d_mois = Decompte.objects.filter(
        statut=Decompte.STATUT_VALIDE, annee=today.year, mois=today.month
    ).aggregate(s=Sum('montant_total'))['s'] or Decimal('0.00')
    d_prec = Decompte.objects.filter(
        statut=Decompte.STATUT_VALIDE, annee=a_prec, mois=m_prec
    ).aggregate(s=Sum('montant_total'))['s'] or Decimal('0.00')
    dir_dec, pct_dec = tendance(d_mois, d_prec)

    # Total payé année
    total_paye_annee = Paiement.objects.filter(
        statut=Paiement.STATUT_ENREGISTRE, date_paiement__year=today.year
    ).aggregate(s=Sum('montant'))['s'] or Decimal('0.00')

    montants = {
        'reste_a_payer': reste_a_payer,
        'total_paye_annee': total_paye_annee,
        'total_paye_mois': total_paye_mois,
        'total_decomptes_annee': Decompte.objects.filter(
            statut=Decompte.STATUT_VALIDE, annee=today.year
        ).aggregate(s=Sum('montant_total'))['s'] or Decimal('0.00'),
        'total_decomptes_mois': d_mois,
        'tendance_paye_dir': dir_paye,
        'tendance_paye_pct': pct_paye,
        'tendance_decompte_dir': dir_dec,
        'tendance_decompte_pct': pct_dec,
    }

    # ---------------- Activité récente + filtre B2 ----------------
    filtre_activite = request.GET.get('activite', '').strip().upper()
    qs_activite = JournalAudit.objects.select_related('id_utilisateur')
    if filtre_activite in ('CREATION', 'MODIFICATION', 'ANNULATION', 'VALIDATION', 'EXPORT'):
        qs_activite = qs_activite.filter(action=filtre_activite)
    activite = qs_activite.order_by('-date_action')[:10]

    # Compteurs pour les chips
    compteurs_activite = {
        'total': JournalAudit.objects.count(),
        'CREATION': JournalAudit.objects.filter(action='CREATION').count(),
        'MODIFICATION': JournalAudit.objects.filter(action='MODIFICATION').count(),
        'EXPORT': JournalAudit.objects.filter(action='EXPORT').count(),
        'ANNULATION': JournalAudit.objects.filter(action='ANNULATION').count(),
        'VALIDATION': JournalAudit.objects.filter(action='VALIDATION').count(),
    }

    # ---------------- Graphique 12 mois (A2) ----------------
    try:
        periode = int(request.GET.get('periode', 12))
    except (ValueError, TypeError):
        periode = 12
    if periode not in (3, 6, 12):
        periode = 12

    evolution_mensuelle = []
    for i in range(periode - 1, -1, -1):
        a, m = _mois_relatif(today.year, today.month, -i)
        total = Paiement_total_mois(a, m)
        evolution_mensuelle.append({
            'annee': a, 'mois': m, 'total': total,
        })
    max_montant = max((m['total'] for m in evolution_mensuelle), default=Decimal('0.00'))
    for m in evolution_mensuelle:
        m['hauteur_pct'] = (float(m['total']) / float(max_montant) * 100) if max_montant > 0 else 0

    # ---------------- Sparklines C2 ----------------
    sparkline = _sparkline_paiements(6)
    max_spark = max(sparkline) if sparkline else 0
    spark_points = []
    if sparkline:
        for i, v in enumerate(sparkline):
            x = (i / max(1, len(sparkline) - 1)) * 100
            y = 100 - ((v / max_spark) * 90 if max_spark > 0 else 0) - 5
            spark_points.append(f"{x:.1f},{y:.1f}")
    sparkline_path = " ".join(spark_points)

    # ---------------- Permissions ----------------
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
        'evolution_mensuelle': evolution_mensuelle,
        'periode': periode,
        'permissions': permissions,
        'compteurs_activite': compteurs_activite,
        'filtre_activite': filtre_activite,
        'sparkline_path': sparkline_path,
        'sparkline_max': max_spark,
    })


@login_required
def global_search(request):
    """Recherche transverse dans les principales entités visibles."""
    q = request.GET.get('q', '').strip()
    results = {'q': q, 'agents': [], 'missions': [], 'gardes': [],
               'decomptes': [], 'ordres_paiement': [], 'total': 0}

    if q and len(q) >= 2:
        if request.user.has_perm('agents.view_agent'):
            from agents.models import Agent
            results['agents'] = list(Agent.objects.filter(
                Q(matricule__icontains=q) | Q(nom__icontains=q)
                | Q(prenoms__icontains=q) | Q(cin__icontains=q)
            ).order_by('nom', 'prenoms')[:10])

        if request.user.has_perm('missions.view_mission'):
            from missions.models import Mission
            results['missions'] = list(Mission.objects.filter(
                Q(numero_officiel__icontains=q) | Q(libelle__icontains=q)
                | Q(lieu__icontains=q)
            ).order_by('-date_debut')[:10])

        if request.user.has_perm('gardes.view_garde'):
            from gardes.models import Garde
            results['gardes'] = list(Garde.objects.filter(
                Q(agent__matricule__icontains=q) | Q(agent__nom__icontains=q)
                | Q(agent__prenoms__icontains=q)
            ).select_related('agent').order_by('-date_heure_debut')[:10])

        if request.user.has_perm('decomptes.view_decompte'):
            from decomptes.models import Decompte
            results['decomptes'] = list(Decompte.objects.filter(
                Q(agent__matricule__icontains=q) | Q(agent__nom__icontains=q)
                | Q(agent__prenoms__icontains=q)
            ).select_related('agent').order_by('-annee', '-mois')[:10])

        if request.user.has_perm('paiements.consulter_ordre_paiement'):
            from paiements.models import OrdrePaiement
            results['ordres_paiement'] = list(OrdrePaiement.objects.filter(
                Q(numero_op__icontains=q)
                | Q(agent_beneficiaire__matricule__icontains=q)
                | Q(agent_beneficiaire__nom__icontains=q)
                | Q(agent_beneficiaire__prenoms__icontains=q)
            ).select_related('agent_beneficiaire').order_by('-annee', '-numero_op')[:10])

        results['total'] = sum(len(v) for k, v in results.items() if k != 'q')

    return render(request, 'core/search_results.html', results)
