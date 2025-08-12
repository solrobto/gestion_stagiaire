# migrate_add_role.py
import sqlite3

DB = "stagiaires.db"
conn = sqlite3.connect(DB)
cur = conn.cursor()

# check columns
cur.execute("PRAGMA table_info(users)")
cols = [r[1] for r in cur.fetchall()]
if "role" not in cols:
    cur.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user'")
    print("Colonne 'role' ajoutée.")
else:
    print("Colonne 'role' existe déjà.")

if "matricule" not in cols:
    cur.execute("ALTER TABLE users ADD COLUMN matricule TEXT")
    print("Colonne 'matricule' ajoutée.")
else:
    print("Colonne 'matricule' existe déjà.")

conn.commit()
conn.close()
