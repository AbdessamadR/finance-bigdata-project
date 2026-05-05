"""
dw_loader.py
────────────
Charge les données Gold dans PostgreSQL Data Warehouse.
Tables créées :
  - snapshot_marche
  - top_mouvements
  - resume_categorie
  - resume_devise
  - alertes_prix
  - top_cryptos_cap
  - historique_prix    ← données Silver complètes
"""

import os
import sys
import logging
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime

# ── Chemins ───────────────────────────────────────────────
BASE_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOLD_DIR   = os.path.join(BASE_DIR, "data", "gold")
SILVER_DIR = os.path.join(BASE_DIR, "data", "silver")
LOGS_DIR   = os.path.join(BASE_DIR, "data", "logs")

os.makedirs(LOGS_DIR, exist_ok=True)

# ── Logging ───────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            os.path.join(LOGS_DIR, "dw_loader.log"),
            encoding="utf-8"
        ),
    ]
)
logger = logging.getLogger(__name__)

# ── Config PostgreSQL DW ──────────────────────────────────
DW_CONFIG = {
    "host":     "localhost",
    "port":     5432,
    "dbname":   "finance_dw",
    "user":     "dw_user",
    "password": "dw_password",
}


# ── Connexion ─────────────────────────────────────────────
def get_conn():
    conn = psycopg2.connect(**DW_CONFIG)
    logger.info("Connexion PostgreSQL DW établie")
    return conn


# ── Création des tables ───────────────────────────────────
def creer_tables(conn):
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS historique_prix (
            id              SERIAL PRIMARY KEY,
            ticker          VARCHAR(20),
            nom             VARCHAR(100),
            prix            DOUBLE PRECISION,
            prix_ouv        DOUBLE PRECISION,
            prix_haut       DOUBLE PRECISION,
            prix_bas        DOUBLE PRECISION,
            volume          DOUBLE PRECISION,
            variation_pct   DOUBLE PRECISION,
            capitalisation  DOUBLE PRECISION,
            devise          VARCHAR(10),
            categorie       VARCHAR(20),
            source          VARCHAR(50),
            date_collecte   VARCHAR(30),
            inserted_at     TIMESTAMP DEFAULT NOW()
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS snapshot_marche (
            id                  SERIAL PRIMARY KEY,
            date_snapshot       VARCHAR(30),
            total_actifs        INTEGER,
            actifs_en_hausse    INTEGER,
            actifs_en_baisse    INTEGER,
            actifs_neutres      INTEGER,
            pct_marche_hausse   DOUBLE PRECISION,
            variation_moyenne   DOUBLE PRECISION,
            variation_mediane   DOUBLE PRECISION,
            meilleure_variation DOUBLE PRECISION,
            pire_variation      DOUBLE PRECISION,
            inserted_at         TIMESTAMP DEFAULT NOW()
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS top_mouvements (
            id              SERIAL PRIMARY KEY,
            ticker          VARCHAR(20),
            nom             VARCHAR(100),
            prix            DOUBLE PRECISION,
            variation_pct   DOUBLE PRECISION,
            devise          VARCHAR(10),
            categorie       VARCHAR(20),
            source          VARCHAR(50),
            type_mouvement  VARCHAR(10),
            inserted_at     TIMESTAMP DEFAULT NOW()
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS resume_categorie (
            id                    SERIAL PRIMARY KEY,
            categorie             VARCHAR(20),
            nb_actifs             INTEGER,
            prix_moyen            DOUBLE PRECISION,
            variation_moyenne     DOUBLE PRECISION,
            variation_max         DOUBLE PRECISION,
            variation_min         DOUBLE PRECISION,
            nb_en_hausse          INTEGER,
            nb_en_baisse          INTEGER,
            volume_total          DOUBLE PRECISION,
            capitalisation_totale DOUBLE PRECISION,
            inserted_at           TIMESTAMP DEFAULT NOW()
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS resume_devise (
            id                SERIAL PRIMARY KEY,
            devise            VARCHAR(10),
            nb_actifs         INTEGER,
            variation_moyenne DOUBLE PRECISION,
            nb_en_hausse      INTEGER,
            nb_en_baisse      INTEGER,
            inserted_at       TIMESTAMP DEFAULT NOW()
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS alertes_prix (
            id              SERIAL PRIMARY KEY,
            ticker          VARCHAR(20),
            nom             VARCHAR(100),
            prix            DOUBLE PRECISION,
            variation_pct   DOUBLE PRECISION,
            niveau_alerte   VARCHAR(20),
            categorie       VARCHAR(20),
            source          VARCHAR(50),
            devise          VARCHAR(10),
            inserted_at     TIMESTAMP DEFAULT NOW()
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS top_cryptos_cap (
            id              SERIAL PRIMARY KEY,
            ticker          VARCHAR(20),
            nom             VARCHAR(100),
            prix            DOUBLE PRECISION,
            capitalisation  DOUBLE PRECISION,
            variation_pct   DOUBLE PRECISION,
            volume          DOUBLE PRECISION,
            inserted_at     TIMESTAMP DEFAULT NOW()
        )
    """)

    conn.commit()
    cur.close()
    logger.info("Tables DW créées ou existantes vérifiées")


# ── Charger un CSV Gold dans une table ───────────────────
def charger_csv_vers_table(conn, nom_fichier: str, nom_table: str):
    chemin = os.path.join(GOLD_DIR, f"{nom_fichier}_latest.csv")
    if not os.path.exists(chemin):
        logger.warning(f"Fichier introuvable : {chemin}")
        return 0

    df = pd.read_csv(chemin, encoding="utf-8-sig")
    if df.empty:
        logger.warning(f"Fichier vide : {chemin}")
        return 0

    # Colonnes de la table (sans id et inserted_at)
    colonnes_tables = {
        "snapshot_marche":  ["date_snapshot", "total_actifs", "actifs_en_hausse",
                             "actifs_en_baisse", "actifs_neutres", "pct_marche_hausse",
                             "variation_moyenne", "variation_mediane",
                             "meilleure_variation", "pire_variation"],
        "top_mouvements":   ["ticker", "nom", "prix", "variation_pct",
                             "devise", "categorie", "source", "type_mouvement"],
        "resume_categorie": ["categorie", "nb_actifs", "prix_moyen",
                             "variation_moyenne", "variation_max", "variation_min",
                             "nb_en_hausse", "nb_en_baisse",
                             "volume_total", "capitalisation_totale"],
        "resume_devise":    ["devise", "nb_actifs", "variation_moyenne",
                             "nb_en_hausse", "nb_en_baisse"],
        "alertes_prix":     ["ticker", "nom", "prix", "variation_pct",
                             "niveau_alerte", "categorie", "source", "devise"],
        "top_cryptos_cap":  ["ticker", "nom", "prix", "capitalisation",
                             "variation_pct", "volume"],
    }

    cols = colonnes_tables.get(nom_table, [])
    cols_ok = [c for c in cols if c in df.columns]
    df = df[cols_ok]

    # Remplacer NaN par None
    df = df.where(pd.notna(df), None)

    cur = conn.cursor()
    valeurs = [tuple(row) for row in df.itertuples(index=False)]
    placeholders = ",".join(["%s"] * len(cols_ok))
    query = f"INSERT INTO {nom_table} ({','.join(cols_ok)}) VALUES ({placeholders})"

    execute_values(cur, f"INSERT INTO {nom_table} ({','.join(cols_ok)}) VALUES %s", valeurs)
    conn.commit()
    cur.close()

    logger.info(f"Table {nom_table} : {len(df)} lignes insérées")
    return len(df)


# ── Charger Silver dans historique_prix ──────────────────
def charger_historique(conn):
    chemin = os.path.join(SILVER_DIR, "silver_latest.csv")
    if not os.path.exists(chemin):
        logger.warning("silver_latest.csv introuvable")
        return 0

    df = pd.read_csv(chemin, encoding="utf-8-sig")
    cols = ["ticker", "nom", "prix", "prix_ouv", "prix_haut", "prix_bas",
            "volume", "variation_pct", "capitalisation",
            "devise", "categorie", "source", "date_collecte"]
    cols_ok = [c for c in cols if c in df.columns]
    df = df[cols_ok].where(pd.notna(df[cols_ok]), None)

    cur = conn.cursor()
    valeurs = [tuple(row) for row in df.itertuples(index=False)]
    execute_values(cur,
        f"INSERT INTO historique_prix ({','.join(cols_ok)}) VALUES %s",
        valeurs
    )
    conn.commit()
    cur.close()

    logger.info(f"historique_prix : {len(df)} lignes insérées")
    return len(df)


# ── Pipeline DW complet ───────────────────────────────────
def charger_dw():
    logger.info("=" * 50)
    logger.info("Démarrage chargement Data Warehouse")
    logger.info("=" * 50)

    conn = get_conn()
    creer_tables(conn)

    # Charger toutes les tables Gold
    tables = [
        ("snapshot_marche",  "snapshot_marche"),
        ("top_mouvements",   "top_mouvements"),
        ("resume_categorie", "resume_categorie"),
        ("resume_devise",    "resume_devise"),
        ("alertes_prix",     "alertes_prix"),
        ("top_cryptos_cap",  "top_cryptos_cap"),
    ]

    total = 0
    for nom_fichier, nom_table in tables:
        total += charger_csv_vers_table(conn, nom_fichier, nom_table)

    # Charger historique Silver
    total += charger_historique(conn)

    conn.close()
    logger.info(f"DW chargé : {total} lignes au total")
    logger.info("=" * 50)
    return total


# ── Point d'entrée ────────────────────────────────────────
if __name__ == "__main__":
    pip_install = os.system("pip install psycopg2-binary --quiet")
    charger_dw()