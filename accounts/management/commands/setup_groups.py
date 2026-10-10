"""
Commande idempotente de configuration des groupes et permissions.

Usage :
    python manage.py setup_groups           # crée/met à jour
    python manage.py setup_groups --reset   # retire les permissions avant réassignation

Ne modifie jamais les appartenances des utilisateurs aux groupes.
Ne touche pas aux superutilisateurs.
"""

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.db import transaction


# ===================================================================
# Définition des permissions natives par groupe
# ===================================================================
# Structure : { nom_du_groupe: { app_label: [codename, ...] } }

GROUPES = {
    'Administrateur': {
        'auth': [
            'add_user', 'change_user', 'view_user',
            'add_group', 'change_group', 'view_group',
        ],
        'audit': ['view_journalaudit'],
        'core': ['view_unite', 'view_parametre'],
        # Lecture seule métier
        'agents': ['view_agent', 'view_affectationagent'],
        'missions': ['view_mission', 'view_participationmission'],
        'tarifs': ['view_tarif'],
        'gardes': ['view_garde'],
        'decomptes': ['view_decompte', 'view_lignedecompte'],
        'paiements': [
            'view_ordrepaiement', 'view_periodepaiement', 'view_paiement',
            'view_confirmationreception', 'view_compteurop',
        ],
    },
    'Percepteur': {
        'auth': ['add_user', 'change_user', 'view_user'],
        'audit': ['view_journalaudit'],
        'core': ['view_unite'],
        'agents': [
            'add_agent', 'change_agent', 'view_agent',
            'add_affectationagent', 'change_affectationagent',
            'view_affectationagent',
        ],
        'missions': [
            'add_mission', 'change_mission', 'view_mission',
            'add_participationmission', 'change_participationmission',
            'view_participationmission',
        ],
        'tarifs': ['add_tarif', 'change_tarif', 'view_tarif'],
        'gardes': ['add_garde', 'change_garde', 'view_garde'],
        'decomptes': [
            'add_decompte', 'change_decompte', 'view_decompte',
            'view_lignedecompte',
        ],
        'paiements': [
            # Permissions personnalisées (Meta.permissions)
            'creer_ordre_paiement', 'valider_ordre_paiement',
            'annuler_ordre_paiement', 'enregistrer_paiement',
            'annuler_paiement', 'confirmer_reception',
            'annuler_confirmation', 'consulter_ordre_paiement',
            'cloturer_ordre_paiement',
            # Vues
            'view_ordrepaiement', 'view_periodepaiement', 'view_paiement',
            'view_confirmationreception', 'view_compteurop',
        ],
    },
    'Operateur': {
        'core': ['view_unite'],
        'agents': [
            'add_agent', 'change_agent', 'view_agent',
            'view_affectationagent',
        ],
        'missions': [
            'add_mission', 'change_mission', 'view_mission',
            'add_participationmission', 'change_participationmission',
            'view_participationmission',
        ],
        'tarifs': ['view_tarif'],
        # Pas de change_garde → ne peut pas modifier/annuler
        'gardes': ['add_garde', 'view_garde'],
        # Pas de change_decompte → ne peut pas valider
        'decomptes': ['add_decompte', 'view_decompte'],
        # Uniquement consultation des OP
        'paiements': [
            'consulter_ordre_paiement',
            'view_ordrepaiement', 'view_periodepaiement', 'view_paiement',
            'view_confirmationreception', 'view_compteurop',
        ],
    },
}


# ===================================================================
# Permission personnalisée à créer (non gérée par Django)
# ===================================================================

PERMISSION_CUSTOM_ANNULER_GARDE = {
    'app_label': 'gardes',
    'model': 'garde',
    'codename': 'annuler_garde',
    'name': "Peut annuler une garde",
}

# Groupes auxquels attribuer la permission custom
GROUPES_AVEC_ANNULER_GARDE = ['Percepteur']


class Command(BaseCommand):
    help = "Configure les groupes et permissions (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help="Retire toutes les permissions des groupes avant réassignation.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        reset = options['reset']

        # -----------------------------------------------------------------
        # 1. Créer la permission custom `annuler_garde` si absente
        # -----------------------------------------------------------------
        ct = ContentType.objects.get(
            app_label=PERMISSION_CUSTOM_ANNULER_GARDE['app_label'],
            model=PERMISSION_CUSTOM_ANNULER_GARDE['model'],
        )
        perm_custom, created = Permission.objects.get_or_create(
            codename=PERMISSION_CUSTOM_ANNULER_GARDE['codename'],
            content_type=ct,
            defaults={'name': PERMISSION_CUSTOM_ANNULER_GARDE['name']},
        )
        if created:
            self.stdout.write(self.style.SUCCESS(
                f"Permission custom créée : gardes.{perm_custom.codename}"
            ))
        else:
            self.stdout.write(f"Permission custom déjà présente : gardes.{perm_custom.codename}")

        # -----------------------------------------------------------------
        # 2. Créer / mettre à jour les groupes
        # -----------------------------------------------------------------
        for nom_groupe, permissions_par_app in GROUPES.items():
            groupe, created = Group.objects.get_or_create(name=nom_groupe)
            if created:
                self.stdout.write(self.style.SUCCESS(f"Groupe créé : {nom_groupe}"))
            else:
                self.stdout.write(f"Groupe existant : {nom_groupe}")

            if reset:
                ancien_nombre = groupe.permissions.count()
                groupe.permissions.clear()
                self.stdout.write(f"  → {ancien_nombre} permissions retirées (--reset)")

            # Résoudre chaque permission déclarée
            manquantes = []
            for app_label, codenames in permissions_par_app.items():
                for codename in codenames:
                    try:
                        perm = Permission.objects.get(
                            content_type__app_label=app_label,
                            codename=codename,
                        )
                        groupe.permissions.add(perm)
                    except Permission.DoesNotExist:
                        manquantes.append(f"{app_label}.{codename}")

            # Ajouter la permission custom si le groupe y a droit
            if nom_groupe in GROUPES_AVEC_ANNULER_GARDE:
                groupe.permissions.add(perm_custom)

            if manquantes:
                self.stdout.write(self.style.WARNING(
                    f"  ⚠ Permissions introuvables pour {nom_groupe} : {manquantes}"
                ))

            self.stdout.write(self.style.SUCCESS(
                f"  → {groupe.permissions.count()} permissions attribuées à {nom_groupe}"
            ))

        self.stdout.write(self.style.SUCCESS("\nConfiguration terminée."))
