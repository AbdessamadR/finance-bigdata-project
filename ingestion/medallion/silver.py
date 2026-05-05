"""
silver.py
─────────────────
Couche Silver : nettoie, normalise et fusionne les données Bronze.
Technologies :
  - Python / Pandas : chargement, fusion inter-sources
  - DuckDB / SQL    : nettoyage, validation, transformation finale
"""

import os
import logging
import pandas as pd
import duckdb
from datetime import datetime

# ── Chemins ───────────────────────────────────────────────
BASE_DIR   = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW_DIR    = os.path.join(BASE_DIR, "data", "raw")
SILVER_DIR = os.path.join(BASE_DIR, "data", "silver")
LOGS_DIR   = os.path.join(BASE_DIR, "data", "logs")

os.makedirs(SILVER_DIR, exist_ok=True)
os.makedirs(LOGS_DIR,   exist_ok=True)

# ── Logging ───────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            os.path.join(LOGS_DIR, "silver.log"),
            encoding="utf-8"
        ),
    ]
)
logger = logging.getLogger(__name__)

# ── Table de correspondance Boursorama → Yahoo ────────────
MAPPING_BOURSORAMA = {
    "1rPTTE": "TTE.PA",
    "1rPBN":  "BN.PA",
    "1rPAIR": "AIR.PA",
    "1rPSAN": "SAN.PA",
    "1rPOR":  "OR.PA",
}


# ════════════════════════════════════════════════════════════
#  PARTIE 1 — Python : chargement et fusion
# ════════════════════════════════════════════════════════════

def charger_bronze() -> pd.DataFrame:
    fichiers = [f for f in os.listdir(RAW_DIR) if f.endswith(".csv")]
    if not fichiers:
        logger.warning("Aucun fichier CSV trouvé dans data/raw/")
        return pd.DataFrame()

    dfs = []
    for f in fichiers:
        chemin = os.path.join(RAW_DIR, f)
        try:
            df = pd.read_csv(chemin, encoding="utf-8-sig")
            df["fichier_source"] = f
            dfs.append(df)
            logger.info(f"Chargé : {f} ({len(df)} lignes)")
        except Exception as e:
            logger.error(f"Erreur lecture {f} : {e}")

    df_total = pd.concat(dfs, ignore_index=True)
    logger.info(f"Total Bronze : {len(df_total)} lignes")
    return df_total


def normaliser_colonnes(df: pd.DataFrame) -> pd.DataFrame:
    renommage = {
        "price":                       "prix",
        "current_price":               "prix",
        "close":                       "prix",
        "c":                           "prix",
        "change":                      "variation_pct",
        "price_change_percentage_24h": "variation_pct",
        "P":                           "variation_pct",
        "high_24h":                    "prix_haut",
        "h":                           "prix_haut",
        "low_24h":                     "prix_bas",
        "l":                           "prix_bas",
        "open":                        "prix_ouv",
        "o":                           "prix_ouv",
        "total_volume":                "volume",
        "v":                           "volume",
        "market_cap":                  "capitalisation",
        "symbol":                      "ticker",
        "s":                           "ticker",
        "name":                        "nom",
        "timestamp":                   "date_collecte",
        "collected_at":                "date_collecte",
    }
    df = df.rename(columns={k: v for k, v in renommage.items() if k in df.columns})
    logger.info("Colonnes normalisées")
    return df


def normaliser_tickers_boursorama(df: pd.DataFrame) -> pd.DataFrame:
    if "ticker" not in df.columns:
        return df
    df["ticker"] = df["ticker"].replace(MAPPING_BOURSORAMA)
    if "devise" not in df.columns:
        df["devise"] = "USD"
    df.loc[df["ticker"].str.endswith(".PA", na=False), "devise"] = "EUR"
    logger.info("Tickers Boursorama normalisés")
    return df


def fusionner(df: pd.DataFrame) -> pd.DataFrame:
    if "categorie" not in df.columns or "source" not in df.columns:
        logger.warning("Colonnes manquantes — déduplication simple")
        return df.drop_duplicates(subset=["ticker"], keep="first")

    resultats = []

    # Cryptos : Binance (prix) + CoinGecko (capitalisation)
    cryptos = df[df["categorie"] == "crypto"].copy()
    for ticker in cryptos["ticker"].unique():
        lignes    = cryptos[cryptos["ticker"] == ticker]
        binance   = lignes[lignes["source"] == "binance"]
        coingecko = lignes[lignes["source"] == "coingecko"]
        if not binance.empty:
            base = binance.iloc[0].copy()
            if not coingecko.empty and "capitalisation" in coingecko.columns:
                cap = coingecko.iloc[0].get("capitalisation")
                if pd.notna(cap):
                    base["capitalisation"] = cap
            base["source"] = "binance+coingecko"
        elif not coingecko.empty:
            base = coingecko.iloc[0].copy()
            base["source"] = "coingecko"
        else:
            base = lignes.iloc[0].copy()
        resultats.append(base)

    # Actions FR : Yahoo (prioritaire) + Boursorama (volume)
    actions_fr = df[df["categorie"] == "action_fr"].copy()
    for ticker in actions_fr["ticker"].unique():
        lignes     = actions_fr[actions_fr["ticker"] == ticker]
        yahoo      = lignes[lignes["source"] == "yahoo_finance"]
        boursorama = lignes[lignes["source"] == "boursorama"]
        if not yahoo.empty:
            base = yahoo.iloc[0].copy()
            if not boursorama.empty and "volume" in boursorama.columns:
                vol = boursorama.iloc[0].get("volume")
                if pd.isna(base.get("volume")) and pd.notna(vol):
                    base["volume"] = vol
            base["source"] = "yahoo+boursorama"
        elif not boursorama.empty:
            base = boursorama.iloc[0].copy()
            base["source"] = "boursorama"
        else:
            base = lignes.iloc[0].copy()
        resultats.append(base)

    # Actions US : Yahoo uniquement
    for ticker in df[df["categorie"] == "action"]["ticker"].unique():
        lignes = df[(df["categorie"] == "action") & (df["ticker"] == ticker)]
        yahoo  = lignes[lignes["source"] == "yahoo_finance"]
        resultats.append(yahoo.iloc[0].copy() if not yahoo.empty else lignes.iloc[0].copy())

    # Indices : Yahoo uniquement
    for ticker in df[df["categorie"] == "indice"]["ticker"].unique():
        lignes = df[(df["categorie"] == "indice") & (df["ticker"] == ticker)]
        yahoo  = lignes[lignes["source"] == "yahoo_finance"]
        resultats.append(yahoo.iloc[0].copy() if not yahoo.empty else lignes.iloc[0].copy())

    # Autres catégories
    autres = df[~df["categorie"].isin(["crypto", "action_fr", "action", "indice"])].copy()
    if not autres.empty:
        for _, row in autres.drop_duplicates(subset=["ticker"], keep="first").iterrows():
            resultats.append(row)

    df_final = pd.DataFrame(resultats).reset_index(drop=True)
    logger.info(f"Fusion Python : {len(df)} → {len(df_final)} lignes")
    return df_final


def assurer_colonnes(df: pd.DataFrame) -> pd.DataFrame:
    """Garantit que toutes les colonnes Silver existent, même vides."""
    colonnes = {
        "ticker": "unknown", "nom": None, "prix": None,
        "prix_ouv": None, "prix_haut": None, "prix_bas": None,
        "volume": None, "variation_pct": None, "capitalisation": None,
        "devise": "USD", "categorie": None, "source": None,
        "date_collecte": None, "fichier_source": None, "statut": "succes",
    }
    for col, valeur_defaut in colonnes.items():
        if col not in df.columns:
            df[col] = valeur_defaut
    return df


# ════════════════════════════════════════════════════════════
#  PARTIE 2 — DuckDB / SQL : nettoyage et validation
# ════════════════════════════════════════════════════════════

def nettoyer_avec_duckdb(df: pd.DataFrame) -> pd.DataFrame:
    """
    Transformations SQL sur le DataFrame fusionné :
      Étape 1 : cast des types numériques et texte
      Étape 2 : suppression erreurs + valeurs aberrantes
      Étape 3 : normalisation des devises
      Étape 4 : sélection et tri des colonnes finales
    """
    con = duckdb.connect()
    con.register("bronze_fusion", df)
    logger.info("DuckDB — début des transformations SQL")

    # ── Étape 1 : cast des types ──────────────────────────
    con.execute("""
        CREATE OR REPLACE TABLE silver_step1 AS
        SELECT
            CAST(ticker          AS VARCHAR) AS ticker,
            CAST(nom             AS VARCHAR) AS nom,
            TRY_CAST(prix           AS DOUBLE) AS prix,
            TRY_CAST(prix_ouv       AS DOUBLE) AS prix_ouv,
            TRY_CAST(prix_haut      AS DOUBLE) AS prix_haut,
            TRY_CAST(prix_bas       AS DOUBLE) AS prix_bas,
            TRY_CAST(volume         AS DOUBLE) AS volume,
            TRY_CAST(variation_pct  AS DOUBLE) AS variation_pct,
            TRY_CAST(capitalisation AS DOUBLE) AS capitalisation,
            CAST(devise          AS VARCHAR) AS devise,
            CAST(categorie       AS VARCHAR) AS categorie,
            CAST(source          AS VARCHAR) AS source,
            CAST(date_collecte   AS VARCHAR) AS date_collecte,
            CAST(fichier_source  AS VARCHAR) AS fichier_source,
            CAST(statut          AS VARCHAR) AS statut
        FROM bronze_fusion
    """)
    logger.info("SQL ✓ Étape 1 : types castés")

    # ── Étape 2 : suppression erreurs + aberrations ───────
    con.execute("""
        CREATE OR REPLACE TABLE silver_step2 AS
        SELECT *
        FROM silver_step1
        WHERE (statut = 'succes' OR statut IS NULL)
          AND prix          IS NOT NULL
          AND prix          > 0
          AND variation_pct IS NOT NULL
          AND variation_pct BETWEEN -100 AND 100
    """)
    nb_avant = con.execute("SELECT COUNT(*) FROM silver_step1").fetchone()[0]
    nb_apres = con.execute("SELECT COUNT(*) FROM silver_step2").fetchone()[0]
    logger.info(f"SQL ✓ Étape 2 : {nb_avant} → {nb_apres} lignes (filtrées)")

    # ── Étape 3 : normalisation devise ────────────────────
    con.execute("""
        CREATE OR REPLACE TABLE silver_step3 AS
        SELECT
            ticker, nom,
            prix, prix_ouv, prix_haut, prix_bas,
            volume, variation_pct, capitalisation,
            CASE
                WHEN devise IS NULL OR devise = '' THEN 'USD'
                WHEN ticker LIKE '%.PA'            THEN 'EUR'
                ELSE devise
            END AS devise,
            categorie, source, date_collecte, fichier_source
        FROM silver_step2
    """)
    logger.info("SQL ✓ Étape 3 : devises normalisées")

    # ── Étape 4 : sélection finale triée ─────────────────
    df_silver = con.execute("""
        SELECT
            ticker, nom,
            prix, prix_ouv, prix_haut, prix_bas,
            volume, variation_pct, capitalisation,
            devise, categorie, source,
            date_collecte, fichier_source
        FROM silver_step3
        ORDER BY categorie, ticker
    """).df()

    logger.info(f"SQL ✓ Étape 4 : {len(df_silver)} lignes finales")
    con.close()
    return df_silver


# ════════════════════════════════════════════════════════════
#  PIPELINE SILVER COMPLET
# ════════════════════════════════════════════════════════════

def transformer_silver() -> pd.DataFrame:
    logger.info("=" * 50)
    logger.info("Démarrage pipeline Silver")
    logger.info("=" * 50)

    # Phase 1 : Python
    df = charger_bronze()
    if df.empty:
        return df

    df = normaliser_colonnes(df)
    df = normaliser_tickers_boursorama(df)
    df = fusionner(df)
    df = assurer_colonnes(df)     # garantit toutes les colonnes

    # Phase 2 : DuckDB / SQL
    df = nettoyer_avec_duckdb(df)

    # Sauvegarde
    horodatage    = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    chemin_csv    = os.path.join(SILVER_DIR, f"silver_{horodatage}.csv")
    chemin_latest = os.path.join(SILVER_DIR, "silver_latest.csv")
    df.to_csv(chemin_csv,    index=False, encoding="utf-8-sig")
    df.to_csv(chemin_latest, index=False, encoding="utf-8-sig")

    logger.info(f"Silver sauvegardé : {chemin_csv}")
    logger.info(f"Total lignes Silver : {len(df)}")
    logger.info("=" * 50)
    return df


# ── Point d'entrée ────────────────────────────────────────
if __name__ == "__main__":
    df = transformer_silver()
    if not df.empty:
        print(f"\nAperçu Silver ({len(df)} lignes) :\n")
        cols = ["ticker", "prix", "variation_pct", "devise", "source", "categorie"]
        print(df[[c for c in cols if c in df.columns]].to_string(index=False))
        print(f"\nSources :\n{df['source'].value_counts().to_string()}")
        print(f"\nCatégories :\n{df['categorie'].value_counts().to_string()}")