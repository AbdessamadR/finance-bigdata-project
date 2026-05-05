"""
data_quality.py
───────────────
Contrôles qualité : complétude, cohérence, validité
Sur les couches Bronze, Silver, Gold et Data Warehouse
Génère un rapport JSON dans data/logs/quality_report.json
"""

import os
import json
import logging
import pandas as pd
import psycopg2
from datetime import datetime

# ── Chemins ───────────────────────────────────────────────
BASE_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR    = os.path.join(BASE_DIR, "data", "raw")
SILVER_DIR = os.path.join(BASE_DIR, "data", "silver")
GOLD_DIR   = os.path.join(BASE_DIR, "data", "gold")
LOGS_DIR   = os.path.join(BASE_DIR, "data", "logs")

os.makedirs(LOGS_DIR, exist_ok=True)

# ── Logging ───────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            os.path.join(LOGS_DIR, "data_quality.log"),
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


# ════════════════════════════════════════════════════════════
#  1. COMPLÉTUDE
# ════════════════════════════════════════════════════════════

def verifier_completude(df: pd.DataFrame, nom: str) -> dict:
    resultats = {}
    total = len(df)
    for col in df.columns:
        nb_null = int(df[col].isna().sum())
        pct     = round(nb_null / total * 100, 2) if total > 0 else 0
        statut  = "OK" if pct == 0 else ("WARN" if pct < 20 else "FAIL")
        resultats[col] = {"nb_null": nb_null, "pct_null": pct, "statut": statut}
        if statut != "OK":
            logger.warning(f"[COMPLÉTUDE] {nom}.{col} : {nb_null} nulls ({pct}%)")
    nb_ok   = sum(1 for v in resultats.values() if v["statut"] == "OK")
    nb_warn = sum(1 for v in resultats.values() if v["statut"] == "WARN")
    nb_fail = sum(1 for v in resultats.values() if v["statut"] == "FAIL")
    logger.info(f"[COMPLÉTUDE] {nom} : {nb_ok} OK / {nb_warn} WARN / {nb_fail} FAIL")
    return resultats


# ════════════════════════════════════════════════════════════
#  2. COHÉRENCE
# ════════════════════════════════════════════════════════════

def verifier_coherence(df: pd.DataFrame, nom: str) -> dict:
    resultats = {}

    # Prix haut >= prix bas
    if "prix_haut" in df.columns and "prix_bas" in df.columns:
        df_ok = df[df["prix_haut"].notna() & df["prix_bas"].notna()]
        nb    = int(len(df_ok[df_ok["prix_haut"] < df_ok["prix_bas"]]))
        statut = "OK" if nb == 0 else "FAIL"
        resultats["prix_haut_>=_prix_bas"] = {"nb_violations": nb, "statut": statut}
        if statut == "FAIL":
            logger.error(f"[COHÉRENCE] {nom} : {nb} lignes prix_haut < prix_bas")

    # Prix entre bas et haut
    if all(c in df.columns for c in ["prix", "prix_haut", "prix_bas"]):
        df_ok = df[df["prix"].notna() & df["prix_haut"].notna() & df["prix_bas"].notna()]
        nb    = int(len(df_ok[
            (df_ok["prix"] > df_ok["prix_haut"]) |
            (df_ok["prix"] < df_ok["prix_bas"])
        ]))
        statut = "OK" if nb == 0 else "WARN"
        resultats["prix_dans_fourchette"] = {"nb_violations": nb, "statut": statut}
        if statut != "OK":
            logger.warning(f"[COHÉRENCE] {nom} : {nb} prix hors fourchette")

    # Variation <= 50%
    if "variation_pct" in df.columns:
        nb    = int(len(df[df["variation_pct"].abs() > 50]))
        statut = "OK" if nb == 0 else "WARN"
        resultats["variation_<=_50pct"] = {"nb_violations": nb, "statut": statut}
        if statut != "OK":
            logger.warning(f"[COHÉRENCE] {nom} : {nb} variations > 50%")

    # Volume positif
    if "volume" in df.columns:
        df_vol = df[df["volume"].notna()]
        nb     = int(len(df_vol[df_vol["volume"] < 0]))
        statut = "OK" if nb == 0 else "FAIL"
        resultats["volume_positif"] = {"nb_violations": nb, "statut": statut}
        if statut == "FAIL":
            logger.error(f"[COHÉRENCE] {nom} : {nb} volumes négatifs")

    nb_ok   = sum(1 for v in resultats.values() if v["statut"] == "OK")
    nb_fail = sum(1 for v in resultats.values() if v["statut"] != "OK")
    logger.info(f"[COHÉRENCE] {nom} : {nb_ok} OK / {nb_fail} anomalies")
    return resultats


# ════════════════════════════════════════════════════════════
#  3. VALIDITÉ
# ════════════════════════════════════════════════════════════

def verifier_validite(df: pd.DataFrame, nom: str) -> dict:
    resultats = {}

    # Prix positif
    if "prix" in df.columns:
        df_p  = df[df["prix"].notna()]
        nb    = int(len(df_p[df_p["prix"] <= 0]))
        statut = "OK" if nb == 0 else "FAIL"
        resultats["prix_positif"] = {"nb_violations": nb, "statut": statut}
        if statut == "FAIL":
            logger.error(f"[VALIDITÉ] {nom} : {nb} prix <= 0")

    # Ticker non vide
    if "ticker" in df.columns:
        nb    = int(len(df[df["ticker"].isna() | (df["ticker"] == "")]))
        statut = "OK" if nb == 0 else "FAIL"
        resultats["ticker_non_vide"] = {"nb_violations": nb, "statut": statut}
        if statut == "FAIL":
            logger.error(f"[VALIDITÉ] {nom} : {nb} tickers vides")

    # Devise valide
    if "devise" in df.columns:
        devises_valides = {"USD", "EUR", "GBP", "JPY", "CHF"}
        nb    = int(len(df[
            ~df["devise"].isin(devises_valides) & df["devise"].notna()
        ]))
        statut = "OK" if nb == 0 else "WARN"
        resultats["devise_valide"] = {"nb_violations": nb, "statut": statut}
        if statut != "OK":
            logger.warning(f"[VALIDITÉ] {nom} : {nb} devises non reconnues")

    # Catégorie valide
    if "categorie" in df.columns:
        cats_valides = {"action", "action_fr", "crypto", "indice"}
        nb    = int(len(df[
            ~df["categorie"].isin(cats_valides) & df["categorie"].notna()
        ]))
        statut = "OK" if nb == 0 else "WARN"
        resultats["categorie_valide"] = {"nb_violations": nb, "statut": statut}
        if statut != "OK":
            logger.warning(f"[VALIDITÉ] {nom} : {nb} catégories invalides")

    # Doublons ticker
    if "ticker" in df.columns:
        nb    = int(df.duplicated(subset=["ticker"]).sum())
        statut = "OK" if nb == 0 else "WARN"
        resultats["pas_de_doublons"] = {"nb_violations": nb, "statut": statut}
        if statut != "OK":
            logger.warning(f"[VALIDITÉ] {nom} : {nb} tickers dupliqués")

    nb_ok   = sum(1 for v in resultats.values() if v["statut"] == "OK")
    nb_fail = sum(1 for v in resultats.values() if v["statut"] != "OK")
    logger.info(f"[VALIDITÉ] {nom} : {nb_ok} OK / {nb_fail} anomalies")
    return resultats


# ════════════════════════════════════════════════════════════
#  4. CONTRÔLES DATA WAREHOUSE (SQL)
# ════════════════════════════════════════════════════════════

def verifier_dw() -> dict:
    resultats = {}
    try:
        conn = psycopg2.connect(**DW_CONFIG)
        cur  = conn.cursor()

        # Lignes par table
        tables = ["historique_prix", "snapshot_marche", "top_mouvements",
                  "resume_categorie", "resume_devise", "alertes_prix", "top_cryptos_cap"]
        comptages = {}
        for table in tables:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            comptages[table] = cur.fetchone()[0]
        resultats["nb_lignes_par_table"] = comptages
        logger.info(f"[DW] Lignes : {comptages}")

        # Prix négatifs
        cur.execute("SELECT COUNT(*) FROM historique_prix WHERE prix <= 0")
        nb = cur.fetchone()[0]
        resultats["prix_negatifs"] = {"nb_violations": nb, "statut": "OK" if nb == 0 else "FAIL"}

        # Tickers vides
        cur.execute("SELECT COUNT(*) FROM historique_prix WHERE ticker IS NULL OR ticker = ''")
        nb = cur.fetchone()[0]
        resultats["tickers_vides"] = {"nb_violations": nb, "statut": "OK" if nb == 0 else "FAIL"}

        # Variation aberrante
        cur.execute("SELECT COUNT(*) FROM historique_prix WHERE ABS(variation_pct) > 100")
        nb = cur.fetchone()[0]
        resultats["variation_aberrante"] = {"nb_violations": nb, "statut": "OK" if nb == 0 else "WARN"}

        # Tables vides
        tables_vides = [t for t, nb in comptages.items() if nb == 0]
        resultats["tables_vides"] = {
            "tables": tables_vides,
            "statut": "OK" if not tables_vides else "WARN"
        }

        cur.close()
        conn.close()
        logger.info("[DW] Contrôles terminés")

    except Exception as e:
        logger.error(f"[DW] Erreur connexion : {e}")
        resultats["erreur"] = str(e)

    return resultats


# ════════════════════════════════════════════════════════════
#  PIPELINE QUALITÉ COMPLET
# ════════════════════════════════════════════════════════════

def verifier_qualite():
    logger.info("=" * 50)
    logger.info("Démarrage contrôles qualité")
    logger.info("=" * 50)

    rapport = {
        "date_rapport": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "bronze": {},
        "silver": {},
        "gold":   {},
        "dw":     {}
    }

    # ── Bronze ────────────────────────────────────────────
    logger.info("Contrôle couche Bronze...")
    fichiers_raw = [f for f in os.listdir(RAW_DIR) if f.endswith(".csv")]
    for f in fichiers_raw:
        df = pd.read_csv(os.path.join(RAW_DIR, f), encoding="utf-8-sig")
        rapport["bronze"][f] = {
            "nb_lignes":   len(df),
            "completude":  verifier_completude(df, f),
            "coherence":   verifier_coherence(df, f),
            "validite":    verifier_validite(df, f),
        }

    # ── Silver ────────────────────────────────────────────
    logger.info("Contrôle couche Silver...")
    chemin_silver = os.path.join(SILVER_DIR, "silver_latest.csv")
    if os.path.exists(chemin_silver):
        df_silver = pd.read_csv(chemin_silver, encoding="utf-8-sig")
        rapport["silver"] = {
            "nb_lignes":  len(df_silver),
            "completude": verifier_completude(df_silver, "silver"),
            "coherence":  verifier_coherence(df_silver, "silver"),
            "validite":   verifier_validite(df_silver, "silver"),
        }

    # ── Gold ──────────────────────────────────────────────
    logger.info("Contrôle couche Gold...")
    fichiers_gold = [f for f in os.listdir(GOLD_DIR) if f.endswith("_latest.csv")]
    for f in fichiers_gold:
        df = pd.read_csv(os.path.join(GOLD_DIR, f), encoding="utf-8-sig")
        rapport["gold"][f] = {
            "nb_lignes":  len(df),
            "completude": verifier_completude(df, f),
        }

    # ── Data Warehouse ────────────────────────────────────
    logger.info("Contrôle Data Warehouse...")
    rapport["dw"] = verifier_dw()

    # ── Résumé global ─────────────────────────────────────
    total_fail = 0
    total_warn = 0

    for couche in ["bronze", "silver"]:
        data = rapport[couche]
        if isinstance(data, dict):
            for section in ["completude", "coherence", "validite"]:
                if section in data:
                    for v in data[section].values():
                        if isinstance(v, dict) and "statut" in v:
                            if v["statut"] == "FAIL": total_fail += 1
                            if v["statut"] == "WARN": total_warn += 1

    rapport["resume"] = {
        "total_fail": total_fail,
        "total_warn": total_warn,
        "statut_global": "FAIL" if total_fail > 0 else ("WARN" if total_warn > 0 else "OK")
    }

    # ── Sauvegarde rapport JSON ───────────────────────────
    chemin_rapport = os.path.join(LOGS_DIR, "quality_report.json")
    with open(chemin_rapport, "w", encoding="utf-8") as f:
        json.dump(rapport, f, ensure_ascii=False, indent=2)

    logger.info(f"Rapport sauvegardé : {chemin_rapport}")
    logger.info(f"Statut global : {rapport['resume']['statut_global']}")
    logger.info(f"FAIL : {total_fail} / WARN : {total_warn}")
    logger.info("=" * 50)

    # ── Affichage terminal ────────────────────────────────
    print(f"\n{'=' * 50}")
    print(f"  RAPPORT QUALITÉ DONNÉES")
    print(f"{'=' * 50}")
    print(f"  Date        : {rapport['date_rapport']}")
    print(f"  Statut      : {rapport['resume']['statut_global']}")
    print(f"  FAIL        : {total_fail}")
    print(f"  WARN        : {total_warn}")
    print(f"\n  DW Tables   :")
    for table, nb in rapport["dw"].get("nb_lignes_par_table", {}).items():
        print(f"    {table:<25} {nb} lignes")
    print(f"\n  Rapport complet : {chemin_rapport}")
    print(f"{'=' * 50}\n")

    return rapport


# ── Point d'entrée ────────────────────────────────────────
if __name__ == "__main__":
    verifier_qualite()