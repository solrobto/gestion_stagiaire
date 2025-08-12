# utils/export_pdf_officiel.py
import sqlite3
import locale
import calendar
from datetime import datetime, date
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
import os
locale.setlocale(locale.LC_TIME, 'French_France.1252')
def generate_etat_presences_pdf(db_path, mois, annee, output_filename=None, lieu="ANTANANARIVO"):
    """
    Génère un PDF au format "ÉTAT POUR SERVIR AU PAIEMENT DES INDEMNITÉS DES STAGIAIRES".
    - mois : '01'..'12' ou int
    - annee : '2025' ou int
    - output_filename : chemin du pdf à créer (par défaut 'Etat_Stagiaires_<annee>_<mois>.pdf')
    """
    # Normalisations
    mois = int(mois)
    annee = int(annee)
    jours_mois = calendar.monthrange(annee, mois)[1]

    if output_filename is None:
        output_filename = f"Etat_présences_{annee}_{mois:02d}.pdf"
    tmp_path = output_filename

    # Récupérer données depuis la DB
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Récupérer stagiaires (id, matricule, nom_prenoms, paositra_money)
    cursor.execute("SELECT id, matricule, nom_prenoms, paositra_money FROM stagiaire ORDER BY matricule ASC")
    stagiaires = cursor.fetchall()

    # Récupérer présences du mois (stagiaire_id, date, presence)
    cursor.execute("""
        SELECT stagiaire_id, date, presence
        FROM presences
        WHERE strftime('%m', date) = ? AND strftime('%Y', date) = ?
    """, (f"{mois:02d}", str(annee)))
    pres_rows = cursor.fetchall()
    conn.close()

    # Organiser présences par stagiaire
    pres_by_stagiaire = {s[0]: {d: "0" for d in range(1, jours_mois+1)} for s in stagiaires}
    totals = {s[0]: 0.0 for s in stagiaires}
    for sid, date_str, presence in pres_rows:
        try:
            d = int(date_str.split("-")[2])
        except Exception:
            continue
        val = float(presence)
        # Représentation dans le tableau : "1", "0.5" ou "0"
        affichage = "1" if val == 1 else ("0.5" if val == 0.5 else "0")
        pres_by_stagiaire.setdefault(sid, {i: "0" for i in range(1, jours_mois+1)})[d] = affichage
        totals[sid] = totals.get(sid, 0.0) + val

    # Construire les données du tableau
    # En-tête : N°, MATRICULE, NOM ET PRÉNOMS, Attribution, jours..., T. Jours, PAOSITRA MONEY
    jours_headers = [str(i) for i in range(1, jours_mois+1)]
    header = ["N°", "MATRICULE", "NOM ET PRÉNOMS", "Attribution"] + jours_headers + ["T. Jours", "PAOSITRA MONEY"]
    table_data = [header]

    numero = 1
    for sid, matricule, nom, paositra in stagiaires:
        total = totals.get(sid, 0.0)
        if total == 0:
            # On ignore ce stagiaire car il n'a aucune présence
            continue

        row = [numero, matricule, nom, "Stagiaire"]
        row += [pres_by_stagiaire.get(sid, {}).get(i, "0") for i in range(1, jours_mois+1)]

        total_display = int(total) if float(total).is_integer() else f"{total:.1f}"
        row += [total_display, paositra if paositra is not None else ""]
        table_data.append(row)
        numero += 1


    # Création du PDF avec ReportLab
    doc = SimpleDocTemplate(tmp_path, pagesize=landscape(A4), leftMargin=0*cm, rightMargin=0*cm, topMargin=1*cm, bottomMargin=1*cm)
    styles = getSampleStyleSheet()
    elements = []

    title_style = styles["Title"]
    title_style.fontSize = 14
    title_style.leading = 14

    mois_en_francais = calendar.month_name[int(mois)].upper()
    texte = f"LIEU DE STAGE PRINCIPAL : ANTANANARIVO - {mois_en_francais} {annee}"
    elements.append(Paragraph("ÉTAT POUR SERVIR AU PAIEMENT DES INDEMNITÉS DES STAGIAIRES", title_style))
    elements.append(Paragraph(texte, styles["Heading3"]))
    elements.append(Spacer(1, 0.2*cm))

    # Table : possibilité d'ajuster colonnes
    # Calcul largeurs approximatives : N° (1cm), matricule (2.5cm), nom (7cm), attribution (3cm), jours (0.7cm chacun), total (1.5cm), paositra (3.5cm)
    day_col_width = 0.45*cm
    col_widths = [0.5*cm, 1.5*cm, 7.0*cm, 1.5*cm] + [day_col_width]*jours_mois + [0.8*cm, 2.5*cm]

    table = Table(table_data, colWidths=col_widths, repeatRows=1)

    # Style du tableau
    style = TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.darkgray),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1, -1), 7),
        ('GRID', (0,0), (-1,-1), 0.4, colors.black),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
    ])

    # Colorer les weekends en gris clair
    for day in range(1, jours_mois+1):
        dt_obj = date(annee, mois, day)
        if dt_obj.weekday() in (5,6):  # samedi=5 dimanche=6
            col_idx = 4 + (day-1)
            style.add('BACKGROUND', (col_idx, 1), (col_idx, -1), colors.lightgrey)

    table.setStyle(style)
    elements.append(table)
    elements.append(Spacer(1, 0.5*cm))

    # Footer signatures
    footer_table_data = [
        ["Antananarivo, le ___________", ""],
        ["DIRECTION DES COMPTES POSTAUX", "CHEF DE CENTRE DE L'ÉPARGNE POSTALE"]
    ]
    footer_tbl = Table(footer_table_data, colWidths=[12*cm, 12*cm])
    footer_style = TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 10),
    ])
    footer_tbl.setStyle(footer_style)
    elements.append(Spacer(1, 1*cm))
    elements.append(footer_tbl)

    doc.build(elements)

    return os.path.abspath(tmp_path)
