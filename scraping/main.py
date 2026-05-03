"""
main.py
────────
Point d'entrée principal — orchestre tous les scrapers.

Usage :
    python main.py                     ← collecte tout
    python main.py --source yahoo      ← Yahoo Finance uniquement
    python main.py --source crypto     ← CoinGecko + Binance
    python main.py --source boursorama ← Boursorama uniquement
    python main.py --auto              ← collecte toutes les heures
    python main.py --auto --intervalle 30  ← toutes les 30 minutes
"""

import argparse
import time
import logging
from datetime import datetime

import pandas as pd

import yahoo_finance
import coingecko
import binance
import boursorama
from utils import sauvegarder

logger = logging.getLogger(__name__)


def collecter_tout():
    """
    Lance tous les scrapers et consolide les résultats.
    Retourne un DataFrame avec toutes les données.
    """
    print("\n" + "═" * 58)
    print("   Finance BigData — Collecte complète (4 sources)")
    print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("═" * 58)

    tous = []

    # 1. Yahoo Finance
    df_yahoo = yahoo_finance.scraper_tout()
    tous.append(df_yahoo)

    # 2. CoinGecko
    df_cg, fg = coingecko.scraper_tout()
    tous.append(df_cg)

    # 3. Binance
    df_binance = binance.scraper_tout()
    tous.append(df_binance)

    # 4. Boursorama
    df_bourso = boursorama.scraper_tout()
    tous.append(df_bourso)

    # Consolider tous les DataFrames
    tous_valides = [df for df in tous if not df.empty and not df.isna().all().all()]
    df_final = pd.concat(tous_valides, ignore_index=True)

    # Résumé
    succes  = len(df_final[df_final["statut"] == "succes"])
    erreurs = len(df_final[df_final["statut"] == "erreur"])

    print(f"\n{'─' * 58}")
    print(f"  ✅  Succès  : {succes}")
    print(f"  ❌  Erreurs : {erreurs}")
    if fg:
        print(f"  😱  Fear & Greed : {fg['fear_greed_valeur']}/100 — {fg['fear_greed_label']}")

    # Sauvegarde
    sauvegarder(df_final, prefixe="collecte")

    # Aperçu
    print(f"\n{'─' * 58}")
    print("  Aperçu :\n")
    df_ok  = df_final[df_final["statut"] == "succes"]
    cols   = ["ticker", "nom", "prix", "variation_pct", "categorie", "source"]
    cols_ok = [c for c in cols if c in df_ok.columns]
    print(df_ok[cols_ok].to_string(index=False))

    return df_final


def mode_automatique(intervalle_minutes=60):
    """
    Collecte automatique toutes les N minutes.
    Remplace Airflow pendant la phase d'apprentissage.
    Arrêter avec Ctrl+C.
    """
    print(f"\n🔄  Mode automatique — toutes les {intervalle_minutes} min")
    print("    Ctrl+C pour arrêter\n")

    compteur = 0
    while True:
        compteur += 1
        print(f"\n{'═'*58}")
        print(f"  Run #{compteur} — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        try:
            collecter_tout()
        except Exception as e:
            logger.error(f"Erreur run #{compteur} : {e}")

        print(f"\n  ⏳ Prochaine collecte dans {intervalle_minutes} minutes...")
        time.sleep(intervalle_minutes * 60)


# ── Point d'entrée ────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Finance BigData Scraper")
    parser.add_argument(
        "--source",
        choices=["tout", "yahoo", "crypto", "boursorama"],
        default="tout",
        help="Quelle source collecter (défaut: tout)"
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Mode automatique — collecte répétée"
    )
    parser.add_argument(
        "--intervalle",
        type=int,
        default=60,
        help="Intervalle en minutes pour le mode auto (défaut: 60)"
    )
    args = parser.parse_args()

    if args.auto:
        mode_automatique(args.intervalle)

    elif args.source == "yahoo":
        df = yahoo_finance.scraper_tout()
        sauvegarder(df, prefixe="yahoo")

    elif args.source == "crypto":
        df_cg, fg = coingecko.scraper_tout()
        df_bn     = binance.scraper_tout()
        df        = pd.concat([df_cg, df_bn], ignore_index=True)
        sauvegarder(df, prefixe="crypto")

    elif args.source == "boursorama":
        df = boursorama.scraper_tout()
        sauvegarder(df, prefixe="boursorama")

    else:
        collecter_tout()
