"""
Services de génération des rapports PDF et Excel.

PDF : WeasyPrint, généré en mémoire (BytesIO).
Excel : openpyxl, généré en mémoire (BytesIO).
"""

from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO

from django.db.models import Q
from django.template.loader import render_to_string
from django.utils import timezone
from weasyprint import HTML
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from agents.models import Agent
from audit.models import JournalAudit
from decomptes.models import Decompte
from gardes.models import Garde
from paiements.models import OrdrePaiement, Paiement


# ===================================================================
# Helpers
# ===================================================================

def _date_edition():
    return timezone.localtime(timezone.now())


def _reference_audit(entite, id_entite, action=JournalAudit.ACTION_VALIDATION):
    """Retourne la dernière entrée d'audit correspondant à (entite, id)."""
    return (
        JournalAudit.objects
        .filter(
            entite_concernee=entite,
            id_entite_concernee=id_entite,
            action=action,
        )
        .order_by('-date_action')
        .first()
    )


# ===================================================================
# PDF génériques
# ===================================================================

def _pdf_from_template(template_name, context, base_url=None):
    """Rend un template et retourne les bytes PDF."""
    html = render_to_string(template_name, context)
    pdf_bytes = HTML(string=html, base_url=base_url).write_pdf()
    return pdf_bytes


# ===================================================================
# Rapport 1 — État de décompte
# ===================================================================

def generer_etat_decompte_pdf(decompte):
    """
    Génère le PDF de l'état de décompte d'un agent.

    Retourne un BytesIO contenant le PDF.
    """
    lignes = (
        decompte.lignes
        .select_related('garde', 'tarif', 'garde__agent')
        .order_by('garde__date_heure_debut')
    )

    audit_entry = _reference_audit(
        'decomptes.Decompte', decompte.pk, JournalAudit.ACTION_VALIDATION
    )

    context = {
        'decompte': decompte,
        'lignes': lignes,
        'audit_entry': audit_entry,
        'date_edition': _date_edition(),
    }

    pdf_bytes = _pdf_from_template(
        'rapports/pdf/etat_decompte.html', context
    )
    return BytesIO(pdf_bytes)


# ===================================================================
# Rapport 2 — Liste de paiement
# ===================================================================

def generer_liste_paiement_pdf(op):
    """
    Génère le PDF de la liste de paiement pour un OP.

    Un OP concerne un seul agent bénéficiaire : la liste contient donc
    une ligne pour cet agent, avec une colonne signature vide.
    """
    paiements = (
        op.paiements
        .filter(statut=Paiement.STATUT_ENREGISTRE)
        .order_by('date_paiement')
    )

    context = {
        'op': op,
        'agent': op.agent_beneficiaire,
        'paiements': paiements,
        'montant_net_paye': op.montant_net_paye,
        'date_edition': _date_edition(),
    }

    pdf_bytes = _pdf_from_template(
        'rapports/pdf/liste_paiement.html', context
    )
    return BytesIO(pdf_bytes)


# ===================================================================
# Rapport 3 — Historique agent
# ===================================================================

def _bornes_periode(date_debut, date_fin):
    """
    Retourne (debut, fin) en `date`.
    Si non spécifiée : 12 derniers mois.
    """
    if date_fin is None:
        date_fin = date.today()
    if date_debut is None:
        date_debut = date_fin - timedelta(days=365)
    if date_debut > date_fin:
        raise ValueError(
            "La date de début doit être antérieure ou égale à la date de fin."
        )
    return date_debut, date_fin


def collecter_donnees_historique_agent(agent, date_debut, date_fin):
    """
    Retourne un dictionnaire contenant les données consolidées
    pour un agent sur la période.

    Règles :
    - Gardes : 30 dernières, début dans la période.
    - Décomptes : 12 derniers, dont l'année/mois tombe dans la période.
    - OP : 12 derniers, date_creation dans la période.
    - Paiements : tous les paiements des OP concernés.
    """
    debut, fin = _bornes_periode(date_debut, date_fin)

    gardes = (
        Garde.objects
        .filter(
            agent=agent,
            date_heure_debut__date__gte=debut,
            date_heure_debut__date__lte=fin,
        )
        .select_related('mission', 'tarif')
        .order_by('-date_heure_debut')[:30]
    )

    decomptes = (
        Decompte.objects
        .filter(agent=agent)
        .filter(
            Q(annee__gt=debut.year)
            | Q(annee=debut.year, mois__gte=debut.month)
        )
        .filter(
            Q(annee__lt=fin.year)
            | Q(annee=fin.year, mois__lte=fin.month)
        )
        .order_by('-annee', '-mois')[:12]
    )

    ordres = (
        OrdrePaiement.objects
        .filter(
            agent_beneficiaire=agent,
            date_creation__date__gte=debut,
            date_creation__date__lte=fin,
        )
        .order_by('-date_creation')[:12]
    )

    paiements = (
        Paiement.objects
        .filter(ordre_paiement__in=ordres)
        .select_related('ordre_paiement')
        .order_by('-date_paiement')
    )

    return {
        'agent': agent,
        'debut': debut,
        'fin': fin,
        'gardes': gardes,
        'decomptes': decomptes,
        'ordres': ordres,
        'paiements': paiements,
    }


def generer_historique_agent_pdf(agent, date_debut=None, date_fin=None):
    """Génère le PDF de l'historique d'un agent."""
    data = collecter_donnees_historique_agent(agent, date_debut, date_fin)
    data['date_edition'] = _date_edition()
    pdf_bytes = _pdf_from_template(
        'rapports/pdf/historique_agent.html', data
    )
    return BytesIO(pdf_bytes)


# ===================================================================
# Rapport 3 — Historique agent (Excel)
# ===================================================================

_ENTETE_STYLE = Font(bold=True, color="FFFFFF")
_ENTETE_FILL = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
_BORDER = Border(
    left=Side(style='thin', color='CCCCCC'),
    right=Side(style='thin', color='CCCCCC'),
    top=Side(style='thin', color='CCCCCC'),
    bottom=Side(style='thin', color='CCCCCC'),
)


def _ecrire_entete(ws, titres, row=1):
    for col_idx, titre in enumerate(titres, start=1):
        cell = ws.cell(row=row, column=col_idx, value=titre)
        cell.font = _ENTETE_STYLE
        cell.fill = _ENTETE_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = _BORDER


def _ajuster_colonnes(ws):
    for col in ws.columns:
        max_len = 0
        letter = get_column_letter(col[0].column)
        for cell in col:
            if cell.value is not None:
                max_len = max(max_len, len(str(cell.value)))
        ws.column_dimensions[letter].width = min(max_len + 3, 40)


def generer_historique_agent_excel(agent, date_debut=None, date_fin=None):
    """Génère le classeur Excel (.xlsx) de l'historique d'un agent."""
    data = collecter_donnees_historique_agent(agent, date_debut, date_fin)

    wb = Workbook()

    # ------- Feuille 1 : Informations générales -------
    ws_info = wb.active
    ws_info.title = "Agent"
    ws_info["A1"] = "Fiche agent"
    ws_info["A1"].font = Font(bold=True, size=14)
    ws_info["A3"] = "Matricule"
    ws_info["B3"] = agent.matricule
    ws_info["A4"] = "Nom"
    ws_info["B4"] = agent.nom
    ws_info["A5"] = "Prénoms"
    ws_info["B5"] = agent.prenoms
    ws_info["A6"] = "Grade"
    ws_info["B6"] = agent.grade or "—"
    ws_info["A7"] = "Statut"
    ws_info["B7"] = agent.get_statut_agent_display()
    ws_info["A8"] = "Période analysée"
    ws_info["B8"] = f"{data['debut'].isoformat()} → {data['fin'].isoformat()}"
    ws_info["A9"] = "Date d'édition"
    ws_info["B9"] = _date_edition().strftime("%d/%m/%Y %H:%M")
    _ajuster_colonnes(ws_info)

    # ------- Feuille 2 : Gardes -------
    ws_g = wb.create_sheet("Gardes")
    _ecrire_entete(ws_g, [
        "Garde #", "Début", "Fin", "Durée (min)",
        "Partiels", "Conforme", "Tarif (Ar)", "Statut",
    ])
    for i, g in enumerate(data['gardes'], start=2):
        ws_g.cell(row=i, column=1, value=g.pk)
        ws_g.cell(row=i, column=2, value=g.date_heure_debut.replace(tzinfo=None))
        ws_g.cell(row=i, column=3, value=g.date_heure_fin.replace(tzinfo=None))
        ws_g.cell(row=i, column=4, value=g.duree_minutes)
        ws_g.cell(row=i, column=5, value=g.nombre_partiels)
        ws_g.cell(row=i, column=6, value="Oui" if g.conforme else "Non")
        ws_g.cell(row=i, column=7, value=float(g.tarif.montant_partiel) if g.tarif else None)
        ws_g.cell(row=i, column=8, value=g.get_statut_display())
        for col in range(1, 9):
            ws_g.cell(row=i, column=col).border = _BORDER
        ws_g.cell(row=i, column=2).number_format = 'DD/MM/YYYY HH:MM'
        ws_g.cell(row=i, column=3).number_format = 'DD/MM/YYYY HH:MM'
        ws_g.cell(row=i, column=7).number_format = '#,##0.00 "Ar"'
    _ajuster_colonnes(ws_g)

    # ------- Feuille 3 : Décomptes -------
    ws_d = wb.create_sheet("Decomptes")
    _ecrire_entete(ws_d, [
        "Décompte #", "Période", "Gardes retenues",
        "Non conformes exclues", "Montant total (Ar)", "Statut",
    ])
    for i, d in enumerate(data['decomptes'], start=2):
        ws_d.cell(row=i, column=1, value=d.pk)
        ws_d.cell(row=i, column=2, value=f"{d.mois:02d}/{d.annee}")
        ws_d.cell(row=i, column=3, value=d.nombre_gardes_retunes)
        ws_d.cell(row=i, column=4, value=d.nombre_gardes_non_conformes_exclues)
        ws_d.cell(row=i, column=5, value=float(d.montant_total))
        ws_d.cell(row=i, column=6, value=d.get_statut_display())
        for col in range(1, 7):
            ws_d.cell(row=i, column=col).border = _BORDER
        ws_d.cell(row=i, column=5).number_format = '#,##0.00 "Ar"'
    _ajuster_colonnes(ws_d)

    # ------- Feuille 4 : OP et Paiements -------
    ws_op = wb.create_sheet("OP et Paiements")
    _ecrire_entete(ws_op, [
        "N° OP", "Date OP", "Montant total (Ar)", "Net payé (Ar)",
        "Statut OP", "Clôturé", "Paiement date", "Paiement montant (Ar)",
        "Mode paiement", "Statut paiement",
    ])
    row = 2
    for op in data['ordres']:
        paiements_op = list(op.paiements.all())
        if not paiements_op:
            paiements_op = [None]
        for p in paiements_op:
            ws_op.cell(row=row, column=1, value=op.numero_op)
            ws_op.cell(row=row, column=2, value=op.date_creation.replace(tzinfo=None))
            ws_op.cell(row=row, column=3, value=float(op.montant_total))
            ws_op.cell(row=row, column=4, value=float(op.montant_net_paye))
            ws_op.cell(row=row, column=5, value=op.get_statut_display())
            ws_op.cell(row=row, column=6, value="Oui" if op.cloture_administrative else "Non")
            if p:
                ws_op.cell(row=row, column=7, value=p.date_paiement.replace(tzinfo=None))
                ws_op.cell(row=row, column=8, value=float(p.montant))
                ws_op.cell(row=row, column=9, value=p.get_mode_paiement_display())
                ws_op.cell(row=row, column=10, value=p.get_statut_display())
                ws_op.cell(row=row, column=7).number_format = 'DD/MM/YYYY HH:MM'
                ws_op.cell(row=row, column=8).number_format = '#,##0.00 "Ar"'
            for col in range(1, 11):
                ws_op.cell(row=row, column=col).border = _BORDER
            ws_op.cell(row=row, column=2).number_format = 'DD/MM/YYYY HH:MM'
            ws_op.cell(row=row, column=3).number_format = '#,##0.00 "Ar"'
            ws_op.cell(row=row, column=4).number_format = '#,##0.00 "Ar"'
            row += 1
    _ajuster_colonnes(ws_op)

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer
