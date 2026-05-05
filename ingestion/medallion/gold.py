"""
gold.py
─────────────────
Couche Gold : agrège les données Silver en KPIs.
Technologies : DuckDB / SQL principalement + Python pour sauvegarde.
KPIs produits :
  1. Snapshot global du marché
  2. Top 5 hausses / baisses
  3. Résumé par catégorie
  4. Résumé par devise
  5. Alertes prix (variation > seuil)
  6. Top cryptos par capitalisation
"""

import os
import logging
import pandas as pd
import duckdb
from datetime import datetime

# ── Chemins ───────────────────────────────────────────────
BASE_DIR   = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SILVER_DIR = os.path.join(BASE_DIR, "data", "silver")
GOLD_DIR   = os.path.join(BASE_DIR, "data", "gold")
LOGS_DIR   = os.path.join(BASE_DIR, "data", "logs")

os.makedirs(GOLD_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

# ── Logging ───────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            os.path.join(LOGS_DIR, "gold.log"),
            encoding="utf-8"
        ),
    ]
)
logger = logging.getLogger(__name__)


# ── Charger Silver dans DuckDB ────────────────────────────
def charger_silver_duckdb() -> duckdb.DuckDBPyConnection:
    chemin = os.path.join(SILVER_DIR, "silver_latest.csv")
    if not os.path.exists(chemin):
        logger.error("silver_latest.csv introuvable — lance silver.py d'abord")
        return None

    chemin_sql = chemin.replace("\\", "/")
    con = duckdb.connect()
    con.execute(f"""
        CREATE OR REPLACE TABLE silver AS
        SELECT * FROM read_csv_auto('{chemin_sql}',
            header      = True,
            null_padding = True
        )
    """)
    nb = con.execute("SELECT COUNT(*) FROM silver").fetchone()[0]
    logger.info(f"Silver chargé dans DuckDB : {nb} lignes")
    return con


# ── Sauvegarder un résultat Gold ──────────────────────────
def sauvegarder_gold(df: pd.DataFrame, nom: str):
    if df is None or df.empty:
        logger.warning(f"Données vides — {nom} non sauvegardé")
        return
    horodatage = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    df.to_csv(
        os.path.join(GOLD_DIR, f"{nom}_{horodatage}.csv"),
        index=False, encoding="utf-8-sig"
    )
    df.to_csv(
        os.path.join(GOLD_DIR, f"{nom}_latest.csv"),
        index=False, encoding="utf-8-sig"
    )
    logger.info(f"Gold sauvegardé : {nom}_latest.csv ({len(df)} lignes)")


# ════════════════════════════════════════════════════════════
#  KPIs — calculés en SQL DuckDB
# ════════════════════════════════════════════════════════════

def kpi_snapshot_marche(con) -> pd.DataFrame:
    df = con.execute("""
        SELECT
            STRFTIME(NOW(), '%Y-%m-%d %H:%M:%S')   AS date_snapshot,
            COUNT(*)                                 AS total_actifs,
            SUM(CASE WHEN variation_pct > 0
                THEN 1 ELSE 0 END)                  AS actifs_en_hausse,
            SUM(CASE WHEN variation_pct < 0
                THEN 1 ELSE 0 END)                  AS actifs_en_baisse,
            SUM(CASE WHEN variation_pct = 0
                THEN 1 ELSE 0 END)                  AS actifs_neutres,
            ROUND(
                100.0 * SUM(CASE WHEN variation_pct > 0
                THEN 1 ELSE 0 END) / COUNT(*), 1
            )                                        AS pct_marche_hausse,
            ROUND(AVG(variation_pct),    4)          AS variation_moyenne,
            ROUND(MEDIAN(variation_pct), 4)          AS variation_mediane,
            ROUND(MAX(variation_pct),    2)          AS meilleure_variation,
            ROUND(MIN(variation_pct),    2)          AS pire_variation
        FROM silver
        WHERE variation_pct IS NOT NULL
    """).df()
    logger.info("SQL ✓ KPI 1 : Snapshot marché")
    return df


def kpi_top_mouvements(con, n: int = 5) -> pd.DataFrame:
    df = con.execute(f"""
        SELECT ticker, nom, prix, variation_pct,
               devise, categorie, source,
               'hausse' AS type_mouvement
        FROM (
            SELECT * FROM silver
            WHERE variation_pct IS NOT NULL
            ORDER BY variation_pct DESC
            LIMIT {n}
        ) top_h

        UNION ALL

        SELECT ticker, nom, prix, variation_pct,
               devise, categorie, source,
               'baisse' AS type_mouvement
        FROM (
            SELECT * FROM silver
            WHERE variation_pct IS NOT NULL
            ORDER BY variation_pct ASC
            LIMIT {n}
        ) top_b

        ORDER BY variation_pct DESC
    """).df()
    logger.info(f"SQL ✓ KPI 2 : Top {n} mouvements")
    return df


def kpi_resume_categorie(con) -> pd.DataFrame:
    df = con.execute("""
        SELECT
            categorie,
            COUNT(*)                                        AS nb_actifs,
            ROUND(AVG(prix),           4)                   AS prix_moyen,
            ROUND(AVG(variation_pct),  4)                   AS variation_moyenne,
            ROUND(MAX(variation_pct),  4)                   AS variation_max,
            ROUND(MIN(variation_pct),  4)                   AS variation_min,
            SUM(CASE WHEN variation_pct > 0
                THEN 1 ELSE 0 END)                          AS nb_en_hausse,
            SUM(CASE WHEN variation_pct < 0
                THEN 1 ELSE 0 END)                          AS nb_en_baisse,
            ROUND(SUM(volume),         2)                   AS volume_total,
            ROUND(SUM(capitalisation), 2)                   AS capitalisation_totale
        FROM silver
        GROUP BY categorie
        ORDER BY nb_actifs DESC
    """).df()
    logger.info("SQL ✓ KPI 3 : Résumé par catégorie")
    return df


def kpi_resume_devise(con) -> pd.DataFrame:
    df = con.execute("""
        SELECT
            devise,
            COUNT(*)                                        AS nb_actifs,
            ROUND(AVG(variation_pct), 4)                    AS variation_moyenne,
            SUM(CASE WHEN variation_pct > 0
                THEN 1 ELSE 0 END)                          AS nb_en_hausse,
            SUM(CASE WHEN variation_pct < 0
                THEN 1 ELSE 0 END)                          AS nb_en_baisse
        FROM silver
        GROUP BY devise
        ORDER BY nb_actifs DESC
    """).df()
    logger.info("SQL ✓ KPI 4 : Résumé par devise")
    return df


def kpi_alertes_prix(con, seuil: float = 2.0) -> pd.DataFrame:
    df = con.execute(f"""
        SELECT
            ticker,
            nom,
            ROUND(prix,          4) AS prix,
            ROUND(variation_pct, 4) AS variation_pct,
            CASE
                WHEN variation_pct >=  {seuil} THEN 'forte hausse'
                WHEN variation_pct <= -{seuil} THEN 'forte baisse'
            END                     AS niveau_alerte,
            categorie,
            source,
            devise
        FROM silver
        WHERE ABS(variation_pct) >= {seuil}
        ORDER BY variation_pct DESC
    """).df()
    logger.info(f"SQL ✓ KPI 5 : Alertes prix seuil={seuil}% → {len(df)} actifs")
    return df


def kpi_top_cryptos_capitalisation(con, n: int = 5) -> pd.DataFrame:
    df = con.execute(f"""
        SELECT
            ticker,
            nom,
            ROUND(prix,           4) AS prix,
            ROUND(capitalisation, 2) AS capitalisation,
            ROUND(variation_pct,  4) AS variation_pct,
            ROUND(volume,         2) AS volume
        FROM silver
        WHERE categorie     = 'crypto'
          AND capitalisation IS NOT NULL
        ORDER BY capitalisation DESC
        LIMIT {n}
    """).df()
    logger.info(f"SQL ✓ KPI 6 : Top {n} cryptos par capitalisation")
    return df


# ════════════════════════════════════════════════════════════
#  PIPELINE GOLD COMPLET
# ════════════════════════════════════════════════════════════

def transformer_gold():
    logger.info("=" * 50)
    logger.info("Démarrage pipeline Gold (DuckDB/SQL)")
    logger.info("=" * 50)

    con = charger_silver_duckdb()
    if con is None:
        return

    # ── Calcul des KPIs en SQL ────────────────────────────
    df_snapshot  = kpi_snapshot_marche(con)
    df_top       = kpi_top_mouvements(con, n=5)
    df_categorie = kpi_resume_categorie(con)
    df_devise    = kpi_resume_devise(con)
    df_alertes   = kpi_alertes_prix(con, seuil=2.0)
    df_cryptos   = kpi_top_cryptos_capitalisation(con, n=5)

    con.close()

    # ── Sauvegarde CSV ────────────────────────────────────
    sauvegarder_gold(df_snapshot,  "snapshot_marche")
    sauvegarder_gold(df_top,       "top_mouvements")
    sauvegarder_gold(df_categorie, "resume_categorie")
    sauvegarder_gold(df_devise,    "resume_devise")
    sauvegarder_gold(df_alertes,   "alertes_prix")
    sauvegarder_gold(df_cryptos,   "top_cryptos_cap")

    # ── Affichage terminal ────────────────────────────────
    sep = "=" * 58

    print(f"\n{sep}\n  SNAPSHOT MARCHÉ\n{sep}")
    print(df_snapshot.to_string(index=False))

    print(f"\n{sep}\n  TOP 5 HAUSSES / BAISSES\n{sep}")
    cols = ["ticker", "prix", "variation_pct", "type_mouvement", "categorie"]
    print(df_top[[c for c in cols if c in df_top.columns]].to_string(index=False))

    print(f"\n{sep}\n  RÉSUMÉ PAR CATÉGORIE\n{sep}")
    print(df_categorie.to_string(index=False))

    print(f"\n{sep}\n  RÉSUMÉ PAR DEVISE\n{sep}")
    print(df_devise.to_string(index=False))

    if not df_alertes.empty:
        print(f"\n{sep}\n  ALERTES PRIX (variation ≥ 2%)\n{sep}")
        cols_a = ["ticker", "prix", "variation_pct", "niveau_alerte", "categorie"]
        print(df_alertes[[c for c in cols_a if c in df_alertes.columns]].to_string(index=False))

    if not df_cryptos.empty:
        print(f"\n{sep}\n  TOP 5 CRYPTOS PAR CAPITALISATION\n{sep}")
        print(df_cryptos.to_string(index=False))

    logger.info("Pipeline Gold terminé")
    logger.info("=" * 50)


# ── Point d'entrée ────────────────────────────────────────
if __name__ == "__main__":
    transformer_gold()