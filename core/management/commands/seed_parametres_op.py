"""
Commande idempotente de peuplement des paramètres officiels de l'OP.

Usage :
    python manage.py seed_parametres_op

Comportement :
- Crée les paramètres s'ils n'existent pas.
- Si un paramètre existe déjà, sa valeur est PRÉSERVÉE (pas d'écrasement).
- Utilise `--reset` pour écraser les valeurs existantes avec les valeurs de référence.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Parametre


# ===================================================================
# Valeurs officielles par défaut (basées sur le document officiel OP)
# ===================================================================

PARAMETRES_OP = {
    'op.ministere': (
        '21 MEF',
        "Ministère de tutelle."
    ),
    'op.ordonnateur': (
        '00-221-A-000000',
        "Numéro d'ordonnateur."
    ),
    'op.commune_beneficiaire': (
        '00000',
        "Code commune bénéficiaire."
    ),
    'op.code_cf': (
        '0101 220',
        "Code CF."
    ),
    'op.tp_assignataire': (
        '10101 100',
        "TP assignataire."
    ),
    'op.programme': (
        '117',
        "Code programme."
    ),
    'op.activite_projet': (
        '117-1-1-1-01',
        "Code activité projet."
    ),
    'op.imputation_admin': (
        '00-21-7-223-00000',
        "Imputation administrative - CDD."
    ),
    'op.compte': (
        '6241 Indemnités de mission intérieure',
        "Compte comptable."
    ),
    'op.republique': (
        'REPUBLIQUE DE MADAGASCAR',
        "En-tête de la République."
    ),
    'op.code_mission': (
        '220',
        "Code MISSION."
    ),
    'op.budget': (
        '01',
        "Code BUDGET."
    ),
    'op.categorie': (
        '3',
        "Code CATEGORIE."
    ),
    'op.sect_conv': (
        '000 RESSOURCES PROPRES',
        "Secteur / Convention."
    ),
    'op.financement': (
        '110-001-001-A',
        "Code FINANCEMENT."
    ),
    'op.pieces_justificatives': (
        'Ordre de mission — État de décompte',
        "Pièces justificatives mentionnées sur l'OP."
    ),
}


class Command(BaseCommand):
    help = "Peuple les paramètres officiels de l'Ordre de Paiement (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help="Écrase les valeurs existantes avec les valeurs de référence.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        reset = options['reset']

        crees = 0
        maj = 0
        conserves = 0

        for cle, (valeur, description) in PARAMETRES_OP.items():
            obj, created = Parametre.objects.get_or_create(
                cle=cle,
                defaults={'valeur': valeur, 'description': description},
            )
            if created:
                crees += 1
                self.stdout.write(self.style.SUCCESS(f"  + {cle}"))
            elif reset:
                obj.valeur = valeur
                obj.description = description
                obj.save(update_fields=['valeur', 'description'])
                maj += 1
                self.stdout.write(self.style.WARNING(f"  ~ {cle} (écrasé)"))
            else:
                conserves += 1
                self.stdout.write(f"  = {cle} (conservé : {obj.valeur!r})")

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"Terminé. Créés : {crees} | Modifiés : {maj} | Conservés : {conserves}"
        ))
