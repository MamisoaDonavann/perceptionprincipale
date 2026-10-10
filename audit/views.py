"""
Vues de l'application audit.

Lecture seule : consultation du journal.
"""

from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, render

from .models import JournalAudit


@login_required
@permission_required('audit.view_journalaudit', raise_exception=True)
def journal_list(request):
    """Liste paginée du journal d'audit avec filtres."""
    qs = JournalAudit.objects.select_related('id_utilisateur')

    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(
            Q(entite_concernee__icontains=q)
            | Q(commentaire__icontains=q)
            | Q(id_utilisateur__username__icontains=q)
        )

    action = request.GET.get('action', '').strip()
    if action in dict(JournalAudit.ACTIONS_CHOICES):
        qs = qs.filter(action=action)

    entite = request.GET.get('entite', '').strip()
    if entite:
        qs = qs.filter(entite_concernee=entite)

    qs = qs.order_by('-date_action')

    # Liste des entités distinctes pour le filtre
    entites_disponibles = (
        JournalAudit.objects
        .values_list('entite_concernee', flat=True)
        .distinct()
        .order_by('entite_concernee')
    )

    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get('page'))

    return render(request, 'audit/list.html', {
        'page': page,
        'q': q,
        'action': action,
        'entite': entite,
        'actions_choices': JournalAudit.ACTIONS_CHOICES,
        'entites_disponibles': entites_disponibles,
        'total': qs.count(),
    })


@login_required
@permission_required('audit.view_journalaudit', raise_exception=True)
def journal_detail(request, pk):
    """Fiche détaillée d'une entrée du journal."""
    entry = get_object_or_404(
        JournalAudit.objects.select_related('id_utilisateur'), pk=pk
    )
    return render(request, 'audit/detail.html', {'entry': entry})
