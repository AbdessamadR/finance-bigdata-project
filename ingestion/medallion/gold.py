"""
gold.py
─────────────────
Couche Gold : agrège les données Silver en KPIs
prêts pour dashboards et analyses.
Lit depuis data/silver/silver_latest.csv
Sauvegarde dans data/gold/
"""

import os
import logging
import pandas as pd
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


# ── Charger Silver ────────────────────────────────────────
def charger_silver() -> pd.DataFrame:
    chemin = os.path.join(SILVER_DIR, "silver_latest.csv")
    if not os.path.exists(chemin):
        logger.error("silver_latest.csv introuvable — lance silver.py d'abord")
        return pd.DataFrame()
    df = pd.read_csv(chemin, encoding="utf-8-sig")
    for col in ["prix", "variation_pct", "volume", "capitalisation",
                "prix_haut", "prix_bas", "prix_ouv"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    logger.info(f"Silver chargé : {len(df)} lignes")
    return df


# ── KPI 1 : Snapshot global du marché ────────────────────
def snapshot_marche(df: pd.DataFrame) -> pd.DataFrame:
    df_ok = df[df["variation_pct"].notna()]
    nb_hausse = len(df_ok[df_ok["variation_pct"] > 0])
    nb_baisse = len(df_ok[df_ok["variation_pct"] < 0])
    nb_neutre = len(df_ok[df_ok["variation_pct"] == 0])

    meilleur = df_ok.loc[df_ok["variation_pct"].idxmax()]
    pire     = df_ok.loc[df_ok["variation_pct"].idxmin()]

    result = pd.DataFrame([{
        "date_snapshot":      datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "total_actifs":       len(df),
        "actifs_en_hausse":   nb_hausse,
        "actifs_en_baisse":   nb_baisse,
        "actifs_neutres":     nb_neutre,
        "pct_marche_hausse":  round(nb_hausse / len(df_ok) * 100, 1),
        "variation_moyenne":  round(df_ok["variation_pct"].mean(), 4),
        "variation_mediane":  round(df_ok["variation_pct"].median(), 4),
        "meilleur_ticker":    meilleur["ticker"],
        "meilleur_variation": round(meilleur["variation_pct"], 2),
        "pire_ticker":        pire["ticker"],
        "pire_variation":     round(pire["variation_pct"], 2),
    }])
    logger.info("Snapshot marché calculé")
    return result


# ── KPI 2 : Top hausses et baisses ───────────────────────
def top_mouvements(df: pd.DataFrame, n: int = 5) -> pd.DataFrame:
    df_ok = df[df["variation_pct"].notna()].copy()

    top_hausses = (
        df_ok.nlargest(n, "variation_pct")
        [["ticker", "nom", "prix", "variation_pct", "devise", "categorie", "source"]]
        .assign(type_mouvement="hausse")
    )
    top_baisses = (
        df_ok.nsmallest(n, "variation_pct")
        [["ticker", "nom", "prix", "variation_pct", "devise", "categorie", "source"]]
        .assign(type_mouvement="baisse")
    )
    result = pd.concat([top_hausses, top_baisses], ignore_index=True)
    logger.info(f"Top {n} mouvements calculés")
    return result


# ── KPI 3 : Résumé par catégorie ─────────────────────────
def resume_par_categorie(df: pd.DataFrame) -> pd.DataFrame:
    if "categorie" not in df.columns:
        return pd.DataFrame()

    result = (
        df.groupby("categorie")
        .agg(
            nb_actifs         =("ticker",        "count"),
            prix_moyen        =("prix",          "mean"),
            variation_moyenne =("variation_pct", "mean"),
            variation_max     =("variation_pct", "max"),
            variation_min     =("variation_pct", "min"),
            nb_en_hausse      =("variation_pct", lambda x: (x > 0).sum()),
            nb_en_baisse      =("variation_pct", lambda x: (x < 0).sum()),
            volume_total      =("volume",        "sum"),
            capitalisation_totale=("capitalisation", "sum"),
        )
        .round(4)
        .reset_index()
    )
    logger.info(f"Résumé par catégorie : {len(result)} catégories")
    return result


# ── KPI 4 : Résumé par devise ─────────────────────────────
def resume_par_devise(df: pd.DataFrame) -> pd.DataFrame:
    if "devise" not in df.columns:
        return pd.DataFrame()

    result = (
        df.groupby("devise")
        .agg(
            nb_actifs         =("ticker",        "count"),
            variation_moyenne =("variation_pct", "mean"),
            nb_en_hausse      =("variation_pct", lambda x: (x > 0).sum()),
            nb_en_baisse      =("variation_pct", lambda x: (x < 0).sum()),
        )
        .round(4)
        .reset_index()
    )
    logger.info(f"Résumé par devise : {len(result)} devises")
    return result


# ── KPI 5 : Alertes prix ──────────────────────────────────
def alertes_prix(df: pd.DataFrame, seuil: float = 2.0) -> pd.DataFrame:
    alertes = df[df["variation_pct"].abs() >= seuil].copy()
    if alertes.empty:
        logger.info(f"Aucune alerte (seuil {seuil}%)")
        return alertes

    alertes["niveau_alerte"] = alertes["variation_pct"].apply(
        lambda v: "forte hausse" if v >= seuil else "forte baisse"
    )
    alertes = (
        alertes[["ticker", "nom", "prix", "variation_pct",
                 "niveau_alerte", "categorie", "source", "devise"]]
        .sort_values("variation_pct", ascending=False)
        .reset_index(drop=True)
    )
    logger.info(f"Alertes prix (seuil {seuil}%) : {len(alertes)} actifs")
    return alertes


# ── KPI 6 : Top cryptos par capitalisation ───────────────
def top_cryptos_capitalisation(df: pd.DataFrame, n: int = 5) -> pd.DataFrame:
    cryptos = df[
        (df["categorie"] == "crypto") &
        df["capitalisation"].notna()
    ].copy()

    if cryptos.empty:
        return pd.DataFrame()

    result = (
        cryptos.nlargest(n, "capitalisation")
        [["ticker", "nom", "prix", "capitalisation", "variation_pct", "volume"]]
        .reset_index(drop=True)
    )
    logger.info(f"Top {n} cryptos par capitalisation calculés")
    return result


# ── Sauvegarder un DataFrame Gold ────────────────────────
def sauvegarder_gold(df: pd.DataFrame, nom: str):
    if df.empty:
        logger.warning(f"Données vides — {nom} non sauvegardé")
        return
    horodatage = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    chemin     = os.path.join(GOLD_DIR, f"{nom}_{horodatage}.csv")
    latest     = os.path.join(GOLD_DIR, f"{nom}_latest.csv")
    df.to_csv(chemin, index=False, encoding="utf-8-sig")
    df.to_csv(latest, index=False, encoding="utf-8-sig")
    logger.info(f"Gold sauvegardé : {nom}_latest.csv")


# ── Pipeline Gold complet ─────────────────────────────────
def transformer_gold():
    logger.info("=" * 50)
    logger.info("Démarrage pipeline Gold")
    logger.info("=" * 50)

    df = charger_silver()
    if df.empty:
        return

    # Calcul des KPIs
    df_snapshot   = snapshot_marche(df)
    df_top        = top_mouvements(df, n=5)
    df_categorie  = resume_par_categorie(df)
    df_devise     = resume_par_devise(df)
    df_alertes    = alertes_prix(df, seuil=2.0)
    df_cryptos    = top_cryptos_capitalisation(df, n=5)

    # Sauvegarde
    sauvegarder_gold(df_snapshot,  "snapshot_marche")
    sauvegarder_gold(df_top,       "top_mouvements")
    sauvegarder_gold(df_categorie, "resume_categorie")
    sauvegarder_gold(df_devise,    "resume_devise")
    sauvegarder_gold(df_alertes,   "alertes_prix")
    sauvegarder_gold(df_cryptos,   "top_cryptos_cap")

    # ── Affichage terminal ────────────────────────────────
    print("\n" + "=" * 58)
    print("  SNAPSHOT MARCHÉ")
    print("=" * 58)
    print(df_snapshot.to_string(index=False))

    print("\n" + "=" * 58)
    print("  TOP 5 HAUSSES / BAISSES")
    print("=" * 58)
    cols = ["ticker", "prix", "variation_pct", "type_mouvement", "categorie"]
    print(df_top[[c for c in cols if c in df_top.columns]].to_string(index=False))

    print("\n" + "=" * 58)
    print("  RÉSUMÉ PAR CATÉGORIE")
    print("=" * 58)
    print(df_categorie.to_string(index=False))

    print("\n" + "=" * 58)
    print("  RÉSUMÉ PAR DEVISE")
    print("=" * 58)
    print(df_devise.to_string(index=False))

    if not df_alertes.empty:
        print("\n" + "=" * 58)
        print("  ALERTES PRIX (variation > 2%)")
        print("=" * 58)
        cols_a = ["ticker", "prix", "variation_pct", "niveau_alerte", "categorie"]
        print(df_alertes[[c for c in cols_a if c in df_alertes.columns]].to_string(index=False))

    if not df_cryptos.empty:
        print("\n" + "=" * 58)
        print("  TOP 5 CRYPTOS PAR CAPITALISATION")
        print("=" * 58)
        print(df_cryptos.to_string(index=False))

    logger.info("Pipeline Gold terminé")
    logger.info("=" * 50)


# ── Point d'entrée ────────────────────────────────────────
if __name__ == "__main__":
    transformer_gold()