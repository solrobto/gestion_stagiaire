import sqlite3
import calendar
import io
import xlsxwriter

def generate_etat_presences_excel(db_path, mois, annee):
    mois = int(mois)
    annee = int(annee)
    nb_jours = calendar.monthrange(annee, mois)[1]

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()

        # Récupérer stagiaires
        cursor.execute("""
            SELECT id, matricule, nom_prenoms, paositra_money 
            FROM stagiaire 
            ORDER BY matricule ASC
        """)
        stagiaires = cursor.fetchall()

        # Récupérer présences du mois
        cursor.execute("""
            SELECT stagiaire_id, date, presence
            FROM presences
            WHERE strftime('%m', date) = ? 
              AND strftime('%Y', date) = ?
        """, (f"{mois:02d}", str(annee)))
        pres_rows = cursor.fetchall()

    # Initialiser tableau des présences
    pres_by_stagiaire = {s[0]: {d: 0 for d in range(1, nb_jours+1)} for s in stagiaires}
    totals = {s[0]: 0.0 for s in stagiaires}

    for sid, date_str, presence in pres_rows:
        try:
            d = int(date_str.split("-")[2])
        except ValueError:
            continue
        val = float(presence)
        pres_by_stagiaire[sid][d] = val
        totals[sid] += val

    # Préparer Excel en mémoire
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    worksheet = workbook.add_worksheet("Présences")

    # Styles
    header_format = workbook.add_format({'bold': True, 'align': 'center', 'bg_color': '#DCE6F1'})
    cell_center = workbook.add_format({'align': 'center'})

    # Écrire en-tête
    jours_headers = [str(i) for i in range(1, nb_jours+1)]
    header = ["N°", "MATRICULE", "NOM ET PRÉNOMS", "Attribution"] + jours_headers + ["T. Jours", "PAOSITRA MONEY"]
    worksheet.write_row(0, 0, header, header_format)

    # Remplir données
    row_idx = 1
    numero = 1
    for sid, matricule, nom, paositra in stagiaires:
        total = totals[sid]
        if total == 0:
            continue

        row = [numero, matricule, nom, "Stagiaire"]
        row += [str(pres_by_stagiaire[sid][i]).rstrip('0').rstrip('.') if pres_by_stagiaire[sid][i] != 0 else "0"
                for i in range(1, nb_jours+1)]
        total_display = int(total) if total.is_integer() else round(total, 1)
        row += [total_display, paositra or ""]

        worksheet.write_row(row_idx, 0, row, cell_center)
        numero += 1
        row_idx += 1

    # Ajuster largeur colonnes
    worksheet.set_column(0, len(header)-1, 12)

    workbook.close()
    output.seek(0)
    return output
