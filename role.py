import sqlite3

conn = sqlite3.connect("stagiaires.db")
cur = conn.cursor()

# Ajouter la colonne role
cur.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user'")

# Ajouter la colonne matricule (si elle n'existe pas aussi)
cur.execute("ALTER TABLE users ADD COLUMN matricule TEXT")

conn.commit()
conn.close()

print("Colonnes ajoutées avec succès !")
