"""
Context processor pour le fil d'Ariane.
"""

# Mapping (app_name, url_name) → liste de segments
# Chaque segment = (label, url_name_or_None)
BREADCRUMBS = {
    # Dashboard
    ('core', 'dashboard'): [('Tableau de bord', None)],

    # Agents
    ('agents', 'list'):    [('Agents', None)],
    ('agents', 'detail'):  [('Agents', 'agents:list'), ('Fiche agent', None)],
    ('agents', 'create'):  [('Agents', 'agents:list'), ('Nouvel agent', None)],
    ('agents', 'update'):  [('Agents', 'agents:list'), ('Modifier', None)],

    # Missions
    ('missions', 'list'):    [('Missions', None)],
    ('missions', 'detail'):  [('Missions', 'missions:list'), ('Détail', None)],
    ('missions', 'create'):  [('Missions', 'missions:list'), ('Nouvelle', None)],
    ('missions', 'update'):  [('Missions', 'missions:list'), ('Modifier', None)],

    # Tarifs
    ('tarifs', 'list'):    [('Tarifs', None)],
    ('tarifs', 'detail'):  [('Tarifs', 'tarifs:list'), ('Détail', None)],
    ('tarifs', 'create'):  [('Tarifs', 'tarifs:list'), ('Nouveau', None)],
    ('tarifs', 'update'):  [('Tarifs', 'tarifs:list'), ('Modifier', None)],

    # Gardes
    ('gardes', 'list'):    [('Gardes', None)],
    ('gardes', 'detail'):  [('Gardes', 'gardes:list'), ('Détail', None)],
    ('gardes', 'create'):  [('Gardes', 'gardes:list'), ('Nouvelle', None)],
    ('gardes', 'annuler'): [('Gardes', 'gardes:list'), ('Annuler', None)],

    # Décomptes
    ('decomptes', 'list'):    [('Décomptes', None)],
    ('decomptes', 'detail'):  [('Décomptes', 'decomptes:list'), ('Détail', None)],
    ('decomptes', 'create'):  [('Décomptes', 'decomptes:list'), ('Nouveau', None)],
    ('decomptes', 'valider'): [('Décomptes', 'decomptes:list'), ('Valider', None)],

    # Paiements
    ('paiements', 'list'):              [('Ordres de paiement', None)],
    ('paiements', 'detail'):            [('Ordres de paiement', 'paiements:list'), ('Détail', None)],
    ('paiements', 'create'):            [('Ordres de paiement', 'paiements:list'), ('Nouveau', None)],
    ('paiements', 'valider'):           [('Ordres de paiement', 'paiements:list'), ('Valider', None)],
    ('paiements', 'retirer_periode'):   [('Ordres de paiement', 'paiements:list'), ('Retirer une période', None)],
    ('paiements', 'annuler'):           [('Ordres de paiement', 'paiements:list'), ('Annuler', None)],
    ('paiements', 'cloturer'):          [('Ordres de paiement', 'paiements:list'), ('Clôturer', None)],
    ('paiements', 'paiement_create'):   [('Ordres de paiement', 'paiements:list'), ('Nouveau paiement', None)],
    ('paiements', 'paiement_annuler'):  [('Ordres de paiement', 'paiements:list'), ('Annuler paiement', None)],
    ('paiements', 'confirmation_create'):  [('Ordres de paiement', 'paiements:list'), ('Confirmer réception', None)],
    ('paiements', 'confirmation_annuler'): [('Ordres de paiement', 'paiements:list'), ('Annuler confirmation', None)],

    # Rapports
    ('rapports', 'index'):             [('Rapports', None)],
    ('rapports', 'filtres_gardes'):    [('Rapports', 'rapports:index'), ('État des gardes', None)],
    ('rapports', 'filtres_op'):        [('Rapports', 'rapports:index'), ('Liste des OP', None)],
    ('rapports', 'filtres_periode'):   [('Rapports', 'rapports:index'), ('Rapport sur période', None)],

    # Audit
    ('audit', 'list'):   [('Journal d\'audit', None)],
    ('audit', 'detail'): [('Journal d\'audit', 'audit:list'), ('Détail', None)],
}


def breadcrumb(request):
    """
    Fournit `breadcrumb_items` au template : liste de dicts
    {label, url} pour le fil d'Ariane.
    """
    if not request.resolver_match:
        return {'breadcrumb_items': []}

    app_name = request.resolver_match.app_name or ''
    url_name = request.resolver_match.url_name or ''

    key = (app_name, url_name)
    segments = BREADCRUMBS.get(key, [])

    from django.urls import reverse, NoReverseMatch
    items = []
    for label, route in segments:
        if route:
            try:
                items.append({'label': label, 'url': reverse(route)})
            except NoReverseMatch:
                items.append({'label': label, 'url': None})
        else:
            items.append({'label': label, 'url': None})
    return {'breadcrumb_items': items}
