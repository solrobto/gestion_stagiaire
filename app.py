# app.py
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
import sqlite3, os
from datetime import datetime, date, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from utils.export_pdf_officiel import generate_etat_presences_pdf  # (optionnel pour export PDF)
from calendar import monthrange
app = Flask(__name__)
app.secret_key = "CHANGE_THIS_TO_A_RANDOM_SECRET"
DB = "stagiaires.db"
# Déconnexion après 10 minutes d'inactivité
app.permanent_session_lifetime = timedelta(minutes=10)

def db_connect():
    return sqlite3.connect(DB)

def login_required(role=None):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if "user_id" not in session:
                flash("Veuillez vous connecter.", "warning")
                return redirect(url_for("login"))
            if role and session.get("role") != role:
                flash("Accès refusé.", "danger")
                # redirection selon rôle
                if session.get("role") == "user":
                    return redirect(url_for("user_profile"))
                return redirect(url_for("index"))
            return f(*args, **kwargs)
        return wrapper
    return decorator

# ---------------- Authentication ----------------
@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        conn = db_connect(); cur = conn.cursor()
        cur.execute("SELECT id, password, role, matricule FROM users WHERE username = ?", (username,))
        row = cur.fetchone(); conn.close()
        if row and check_password_hash(row[1], password):
            session["user_id"] = row[0]
            session["username"] = username
            session["role"] = row[2]
            session["matricule"] = row[3]  # None for admin
            flash("Connexion réussie.", "success")
            if row[2] == "admin":
                return redirect(url_for("index"))
            else:
                return redirect(url_for("user_profile"))
        flash("Nom d'utilisateur ou mot de passe incorrect.", "danger")
    return render_template("login.html")

@app.route("/register", methods=["GET","POST"])
def register():
    # Permet la création manuelle de comptes (admin ou user)
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        confirm = request.form["confirm"]
        role = request.form.get("role", "user")
        matricule = request.form.get("matricule") or None

        if password != confirm:
            flash("Les mots de passe ne correspondent pas.", "danger")
            return redirect(url_for("register"))
        if role == "user" and not matricule:
            flash("Le matricule est requis pour un utilisateur.", "danger")
            return redirect(url_for("register"))

        hashed = generate_password_hash(password)
        try:
            conn = db_connect(); cur = conn.cursor()
            cur.execute("INSERT INTO users (username, password, role, matricule) VALUES (?, ?, ?, ?)",
                        (username, hashed, role, matricule))
            conn.commit()
            conn.close()
            flash("Compte créé avec succès.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Nom d'utilisateur déjà utilisé.", "danger")
            return redirect(url_for("register"))
    return render_template("register.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Déconnecté.", "info")
    return redirect(url_for("login"))

# ---------------- Admin area ----------------
@app.route("/")
@login_required(role="admin")
def index():
    conn = db_connect(); cur = conn.cursor()
    cur.execute("SELECT id, nom_prenoms, paositra_money, bureau, matricule FROM stagiaire ORDER BY matricule ASC")
    stagiaires = cur.fetchall(); conn.close()
    return render_template("index.html", stagiaires=stagiaires, username=session.get("username"))

# Ajouter stagiaire (optionnel : créer un compte user automatiquement)
@app.route("/ajouter", methods=["POST"])
@login_required(role="admin")
def ajouter():
    nom = request.form.get("nom","").strip()
    bureau = request.form.get("bureau","").strip()
    paositra = request.form.get("paositra","").strip()
    matricule = request.form.get("matricule","").strip()

    if not (nom and bureau and paositra and matricule):
        flash("Tous les champs sont requis.", "warning")
        return redirect(url_for("index"))

    try:
        conn = db_connect(); cur = conn.cursor()
        cur.execute("INSERT INTO stagiaire (nom_prenoms, paositra_money, bureau, matricule) VALUES (?, ?, ?, ?)",
                    (nom, paositra, bureau, matricule))
        # Créer automatiquement l'utilisateur lié (username = matricule, mot de passe initial = matricule)
        try:
            cur.execute("INSERT INTO users (username, password, role, matricule) VALUES (?, ?, ?, ?)",
                        (matricule, generate_password_hash(matricule), "user", matricule))
        except Exception:
            # si username déjà présent, on ignore (on peut logguer)
            pass
        conn.commit(); conn.close()
        flash("Stagiaire ajouté.", "success")
    except sqlite3.IntegrityError:
        flash("PAOSITRA MONEY ou Matricule déjà utilisé.", "danger")
    return redirect(url_for("index"))

@app.route("/modifier/<int:id>", methods=["GET","POST"])
@login_required(role="admin")
def modifier(id):
    conn = db_connect(); cur = conn.cursor()
    if request.method == "POST":
        nom = request.form.get("nom"); bureau = request.form.get("bureau")
        paositra = request.form.get("paositra"); matricule = request.form.get("matricule")
        cur.execute("UPDATE stagiaire SET nom_prenoms=?, paositra_money=?, bureau=?, matricule=? WHERE id=?",
                    (nom, paositra, bureau, matricule, id))
        conn.commit(); conn.close()
        flash("Stagiaire modifié.", "success")
        return redirect(url_for("index"))
    cur.execute("SELECT id, nom_prenoms, paositra_money, bureau, matricule FROM stagiaire WHERE id=?", (id,))
    s = cur.fetchone(); conn.close()
    if not s:
        flash("Stagiaire introuvable.", "danger"); return redirect(url_for("index"))
    return render_template("modifier.html", stagiaire=s)

@app.route("/supprimer/<int:id>")
@login_required(role="admin")
def supprimer(id):
    conn = db_connect(); cur = conn.cursor(); cur.execute("DELETE FROM stagiaire WHERE id=?", (id,)); conn.commit(); conn.close()
    flash("Stagiaire supprimé.", "info"); return redirect(url_for("index"))

# Gestion des présences (admin) par date
def get_stagiaires_simple():
    conn = db_connect(); cur = conn.cursor(); cur.execute("SELECT id, nom_prenoms, matricule FROM stagiaire ORDER BY matricule ASC"); r = cur.fetchall(); conn.close(); return r

def get_presences_for_date(date_str):
    conn = db_connect(); cur = conn.cursor(); cur.execute("SELECT stagiaire_id, presence FROM presences WHERE date = ?", (date_str,)); d = dict(cur.fetchall()); conn.close(); return d

@app.route("/presences", methods=["GET","POST"])
@login_required(role="admin")
def presences():
    stagiaires = get_stagiaires_simple()
    selected_date = request.form.get("date") if request.method=="POST" else date.today().strftime("%Y-%m-%d")
    pres = get_presences_for_date(selected_date)
    if request.method=="POST" and "save_presences" in request.form:
        conn = db_connect(); cur = conn.cursor()
        for s in stagiaires:
            sid = s[0]
            v = request.form.get(f"presence_{sid}")
            if v is not None:
                cur.execute("""INSERT INTO presences (stagiaire_id, date, presence)
                               VALUES (?, ?, ?)
                               ON CONFLICT(stagiaire_id, date)
                               DO UPDATE SET presence=excluded.presence""",
                            (sid, selected_date, float(v)))
        conn.commit(); conn.close(); flash(f"Présences pour {selected_date} enregistrées.", "success")
        pres = get_presences_for_date(selected_date)
    return render_template("presences.html", stagiaires=stagiaires, selected_date=selected_date, presences=pres, username=session.get("username"))


@app.route("/presences_admin", methods=["GET", "POST"])
@login_required(role="admin")
def presences_admin():
    conn = sqlite3.connect(DB)
    cursor = conn.cursor()
    cursor.execute("SELECT id, nom_prenoms, matricule FROM stagiaire ORDER BY nom_prenoms ASC")
    stagiaires = cursor.fetchall()

    selected_id = request.args.get("stagiaire_id")
    selected_month = request.args.get("month", date.today().strftime("%Y-%m"))

    presences_data = {}
    jours = []

    if selected_id:
        year, month = map(int, selected_month.split("-"))
        start_date = date(year, month, 1)
        days_in_month = monthrange(year, month)[1]

        # Générer uniquement les jours ouvrables (lundi à vendredi)
        jours = [
    start_date + timedelta(days=i)
    for i in range(days_in_month)
    if (start_date + timedelta(days=i)).weekday() < 5
]

        # Charger présences existantes
        cursor.execute("""
            SELECT date, presence FROM presences
            WHERE stagiaire_id = ?
            AND strftime('%Y-%m', date) = ?
        """, (selected_id, selected_month))
        presences_data = dict(cursor.fetchall())

    if request.method == "POST":
        selected_id = request.form.get("stagiaire_id")
        selected_month = request.form.get("month")
        year, month = map(int, selected_month.split("-"))
        start_date = date(year, month, 1)
        days_in_month = monthrange(year, month)[1]
        jours = [
            start_date +timedelta(days=i)
            for i in range(days_in_month)
            if (start_date +timedelta(days=i)).weekday() < 5
        ]

        for jour in jours:
            presence_value = 1 if request.form.get(f"presence_{jour}") else 0
            cursor.execute("""
                INSERT INTO presences (stagiaire_id, date, presence)
                VALUES (?, ?, ?)
                ON CONFLICT(stagiaire_id, date) DO UPDATE SET presence = excluded.presence
            """, (selected_id, jour.strftime("%Y-%m-%d"), presence_value))
        conn.commit()
        flash("Présences mises à jour avec succès", "success")
        return redirect(url_for("presences_admin", stagiaire_id=selected_id, month=selected_month))

    conn.close()
    return render_template("presences_admin.html", stagiaires=stagiaires, jours=jours,
                           presences_data=presences_data,
                           selected_id=selected_id, selected_month=selected_month)

# ---------------- User area ----------------
@app.route("/user/profile")
@login_required(role="user")
def user_profile():
    matricule = session.get("matricule")
    conn = db_connect(); cur = conn.cursor()
    cur.execute("SELECT id, nom_prenoms, matricule FROM stagiaire WHERE matricule = ?", (matricule,))
    s = cur.fetchone(); conn.close()
    return render_template("user_profile.html", stagiaire=s, username=session.get("username"))

@app.route("/user/presence", methods=["POST"])
@login_required(role="user")
def user_presence():
    matricule = session.get("matricule")
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    conn = db_connect(); cur = conn.cursor()
    cur.execute("SELECT id FROM stagiaire WHERE matricule = ?", (matricule,))
    row = cur.fetchone()
    if not row:
        conn.close(); flash("Profil stagiaire introuvable.", "danger"); return redirect(url_for("user_profile"))
    sid = row[0]
    cur.execute("SELECT 1 FROM presences WHERE stagiaire_id = ? AND date = ?", (sid, date_str))
    if cur.fetchone():
        conn.close(); flash("Présence déjà enregistrée aujourd'hui.", "info"); return redirect(url_for("user_profile"))
    cur.execute("INSERT INTO presences (stagiaire_id, date, presence) VALUES (?, ?, ?)", (sid, date_str, 1.0))
    conn.commit(); conn.close(); flash("Présence enregistrée !", "success"); return redirect(url_for("user_profile"))

@app.route("/user/presences")
@login_required(role="user")
def user_presences():
    user_id = session.get("user_id")
    mois = request.args.get("mois", date.today().strftime("%Y-%m"))
    conn = sqlite3.connect(DB)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT date, presence FROM presences
        WHERE stagiaire_id = ? AND strftime('%Y-%m', date) = ?
        ORDER BY date ASC
    """, (user_id, mois))
    presences = cursor.fetchall()
    return render_template("user_presences.html", presences=presences, mois_selectionne=mois)

# ---------------- Recap & Export (admin) ----------------
@app.route("/recap", methods=["GET","POST"])
@login_required(role="admin")
def recap():
    mois = request.form.get("mois", datetime.today().strftime("%m"))
    annee = request.form.get("annee", datetime.today().strftime("%Y"))
    conn = db_connect(); cur = conn.cursor()
    cur.execute("""SELECT s.nom_prenoms, s.matricule, s.bureau, IFNULL(SUM(p.presence),0) as total_jours
                   FROM stagiaire s
                   LEFT JOIN presences p ON s.id = p.stagiaire_id
                       AND strftime('%m', p.date) = ? AND strftime('%Y', p.date) = ?
                   GROUP BY s.id ORDER BY s.matricule""", (mois, annee))
    data = cur.fetchall(); conn.close()
    return render_template("recap.html", recap_data=data, mois=mois, annee=annee, username=session.get("username"))

@app.route("/export/presences/pdf", methods=["GET","POST"])
@login_required(role="admin")
def export_presences_pdf():
    if request.method == "POST":
        mois = request.form.get("mois"); annee = request.form.get("annee")
        output = generate_etat_presences_pdf(DB, mois, annee)
        if os.path.exists(output):
            return send_file(output, as_attachment=True, download_name=os.path.basename(output))
        flash("Erreur génération PDF", "danger"); return redirect(url_for("export_presences_pdf"))
    return render_template("export_presences_pdf.html", username=session.get("username"))

if __name__ == "__main__":
    app.run(debug=True)
