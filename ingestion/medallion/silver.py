"""
silver.py
─────────────────
Couche Silver : nettoie, normalise et fusionne les données Bronze.
Stratégie de fusion :
  - Cryptos     : prix Binance + market_cap CoinGecko
  - Actions FR  : Yahoo prioritaire + volume Boursorama en complément
  - Actions US  : Yahoo Finance uniquement
  - Indices     : Yahoo Finance uniquement
"""

import os
import logging
import pandas as pd
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
    "1rPTTE":  "TTE.PA",
    "1rPBN":   "BN.PA",
    "1rPAIR":  "AIR.PA",
    "1rPSAN":  "SAN.PA",
    "1rPOR":   "OR.PA",
}


# ── Étape 1 : Charger tous les CSV bruts ─────────────────
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


# ── Étape 2 : Supprimer les erreurs ──────────────────────
def supprimer_erreurs(df: pd.DataFrame) -> pd.DataFrame:
    avant = len(df)
    if "statut" in df.columns:
        df = df[df["statut"] == "succes"].copy()
    logger.info(f"Erreurs supprimées : {avant - len(df)} lignes")
    return df


# ── Étape 3 : Normaliser les colonnes ────────────────────
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


# ── Étape 4 : Normaliser les dates ───────────────────────
def normaliser_dates(df: pd.DataFrame) -> pd.DataFrame:
    if "date_collecte" not in df.columns:
        df["date_collecte"] = datetime.utcnow().isoformat()
        return df

    def parser_date(val):
        if pd.isna(val):
            return pd.NaT
        try:
            if str(val).isdigit() and len(str(val)) == 13:
                return pd.to_datetime(int(val), unit="ms")
            return pd.to_datetime(val)
        except Exception:
            return pd.NaT

    df["date_collecte"] = df["date_collecte"].apply(parser_date)
    df["date_collecte"] = pd.to_datetime(
        df["date_collecte"], utc=True, errors="coerce"
    ).dt.strftime("%Y-%m-%d %H:%M:%S")

    logger.info("Dates normalisées")
    return df


# ── Étape 5 : Valider les prix ────────────────────────────
def valider_prix(df: pd.DataFrame) -> pd.DataFrame:
    avant = len(df)
    cols_num = ["prix", "prix_haut", "prix_bas", "prix_ouv",
                "volume", "variation_pct", "capitalisation"]
    for col in cols_num:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "prix" in df.columns:
        df = df[df["prix"].notna() & (df["prix"] > 0)]
    if "variation_pct" in df.columns:
        df = df[df["variation_pct"].between(-100, 100, inclusive="both")]

    logger.info(f"Valeurs aberrantes supprimées : {avant - len(df)} lignes")
    return df


# ── Étape 6 : Normaliser les devises ─────────────────────
def normaliser_devises(df: pd.DataFrame) -> pd.DataFrame:
    if "devise" not in df.columns:
        df["devise"] = "USD"
    if "ticker" in df.columns:
        df.loc[df["ticker"].str.endswith(".PA", na=False), "devise"] = "EUR"
    logger.info("Devises normalisées")
    return df


# ── Étape 7 : Normaliser les tickers Boursorama ──────────
def normaliser_tickers_boursorama(df: pd.DataFrame) -> pd.DataFrame:
    if "ticker" not in df.columns:
        return df
    df["ticker"] = df["ticker"].replace(MAPPING_BOURSORAMA)
    # Mettre à jour la devise des tickers renommés
    df.loc[df["ticker"].str.endswith(".PA", na=False), "devise"] = "EUR"
    logger.info("Tickers Boursorama normalisés")
    return df


# ── Étape 8 : Fusion intelligente ────────────────────────
def fusionner(df: pd.DataFrame) -> pd.DataFrame:
    if "categorie" not in df.columns or "source" not in df.columns:
        logger.warning("Colonnes manquantes — déduplication simple")
        return df.drop_duplicates(subset=["ticker"], keep="first")

    resultats = []

    # ── Cryptos : Binance + CoinGecko ────────────────────
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

    # ── Actions FR : Yahoo + Boursorama ──────────────────
    actions_fr = df[df["categorie"] == "action_fr"].copy()
    for ticker in actions_fr["ticker"].unique():
        lignes     = actions_fr[actions_fr["ticker"] == ticker]
        yahoo      = lignes[lignes["source"] == "yahoo_finance"]
        boursorama = lignes[lignes["source"] == "boursorama"]

        if not yahoo.empty:
            base = yahoo.iloc[0].copy()
            # Complément volume depuis Boursorama si manquant
            if not boursorama.empty:
                if "volume" in boursorama.columns:
                    vol_bourso = boursorama.iloc[0].get("volume")
                    if pd.isna(base.get("volume")) and pd.notna(vol_bourso):
                        base["volume"] = vol_bourso
            base["source"] = "yahoo+boursorama"
        elif not boursorama.empty:
            base = boursorama.iloc[0].copy()
            base["source"] = "boursorama"
        else:
            base = lignes.iloc[0].copy()

        resultats.append(base)

    # ── Actions US : Yahoo uniquement ────────────────────
    actions_us = df[df["categorie"] == "action"].copy()
    for ticker in actions_us["ticker"].unique():
        lignes = actions_us[actions_us["ticker"] == ticker]
        yahoo  = lignes[lignes["source"] == "yahoo_finance"]
        base   = yahoo.iloc[0].copy() if not yahoo.empty else lignes.iloc[0].copy()
        resultats.append(base)

    # ── Indices : Yahoo uniquement ────────────────────────
    indices = df[df["categorie"] == "indice"].copy()
    for ticker in indices["ticker"].unique():
        lignes = indices[indices["ticker"] == ticker]
        yahoo  = lignes[lignes["source"] == "yahoo_finance"]
        base   = yahoo.iloc[0].copy() if not yahoo.empty else lignes.iloc[0].copy()
        resultats.append(base)

    # ── Autres catégories ─────────────────────────────────
    categories_connues = ["crypto", "action_fr", "action", "indice"]
    autres = df[~df["categorie"].isin(categories_connues)].copy()
    if not autres.empty:
        for _, row in autres.drop_duplicates(subset=["ticker"], keep="first").iterrows():
            resultats.append(row)

    df_final = pd.DataFrame(resultats).reset_index(drop=True)
    logger.info(f"Fusion terminée : {len(df)} → {len(df_final)} lignes")
    return df_final


# ── Étape 9 : Sélectionner les colonnes finales ──────────
def selectionner_colonnes(df: pd.DataFrame) -> pd.DataFrame:
    colonnes_silver = [
        "ticker", "nom", "prix", "prix_ouv", "prix_haut", "prix_bas",
        "volume", "variation_pct", "capitalisation",
        "devise", "categorie", "source", "date_collecte", "fichier_source"
    ]
    return df[[c for c in colonnes_silver if c in df.columns]]


# ── Pipeline Silver complet ───────────────────────────────
def transformer_silver() -> pd.DataFrame:
    logger.info("=" * 50)
    logger.info("Démarrage pipeline Silver")
    logger.info("=" * 50)

    df = charger_bronze()
    if df.empty:
        return df

    df = supprimer_erreurs(df)
    df = normaliser_colonnes(df)
    df = normaliser_dates(df)
    df = valider_prix(df)
    df = normaliser_devises(df)
    df = normaliser_tickers_boursorama(df)
    df = fusionner(df)
    df = selectionner_colonnes(df)

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
        cols_ok = [c for c in cols if c in df.columns]
        print(df[cols_ok].to_string(index=False))

        print(f"\nSources utilisées :\n")
        print(df["source"].value_counts().to_string())

        print(f"\nCatégories :\n")
        print(df["categorie"].value_counts().to_string())