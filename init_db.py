
import sqlite3
conn = sqlite3.connect("stagiaires.db")
c = conn.cursor()
c.execute("""CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    role TEXT NOT NULL,
    matricule TEXT
)""")
c.execute("""CREATE TABLE IF NOT EXISTS stagiaire (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nom_prenoms TEXT NOT NULL,
    paositra_money TEXT UNIQUE NOT NULL,
    bureau TEXT NOT NULL,
    matricule TEXT UNIQUE NOT NULL
)""")
c.execute("""CREATE TABLE IF NOT EXISTS presences (
    stagiaire_id INTEGER NOT NULL,
    date TEXT NOT NULL,
    presence REAL NOT NULL,
    time TEXT,
    PRIMARY KEY (stagiaire_id, date)
)""")
conn.commit()
conn.close()
print("Base initialisée : users, stagiaire, presences")
