"""
yahoo_finance.py
─────────────────
Scrappe les données depuis Yahoo Finance :
  - Actions US
  - Indices boursiers
  - Actions françaises (.PA)
  - Cryptos (optionnel)

Usage autonome :
    python yahoo_finance.py
"""

import time
import logging

import yfinance as yf

from config import TICKERS_ACTIONS, TICKERS_INDICES, TICKERS_FR, DELAI_YAHOO
from utils  import arrondir, en_int, variation_pct, maintenant, afficher_record, sauvegarder

import pandas as pd

logger = logging.getLogger(__name__)


def scraper_ticker(ticker, categorie):
    """
    Scrappe un seul ticker Yahoo Finance.

    Paramètres :
        ticker    : symbole boursier (ex: "AAPL", "^GSPC", "TTE.PA")
        categorie : "action", "indice", "action_fr", "crypto"

    Retourne :
        dict avec toutes les données du ticker
    """
    try:
        info = yf.Ticker(ticker).fast_info
        prix = arrondir(info.last_price)
        prev = arrondir(info.previous_close)

        return {
            "ticker":         ticker,
            "nom":            "",
            "prix":           prix,
            "ouverture":      arrondir(info.open),
            "haut":           arrondir(info.day_high),
            "bas":            arrondir(info.day_low),
            "cloture_veille": prev,
            "variation_pct":  variation_pct(prix, prev),
            "variation_1h":   None,
            "variation_7j":   None,
            "volume":         en_int(info.last_volume),
            "market_cap":     en_int(info.market_cap),
            "rang":           None,
            "ath":            None,
            "supply":         None,
            "bid":            None,
            "ask":            None,
            "devise":         info.currency or "USD",
            "categorie":      categorie,
            "source":         "yahoo_finance",
            "statut":         "succes",
            "collecte_le":    maintenant(),
        }

    except Exception as e:
        logger.warning(f"Yahoo — {ticker} : {e}")
        return {
            "ticker":      ticker,
            "categorie":   categorie,
            "source":      "yahoo_finance",
            "statut":      "erreur",
            "erreur_msg":  str(e),
            "collecte_le": maintenant(),
        }


def scraper_liste(tickers, categorie):
    """
    Scrappe une liste de tickers.
    Affiche chaque résultat et retourne une liste de dicts.
    """
    resultats = []
    for ticker in tickers:
        data = scraper_ticker(ticker, categorie)
        resultats.append(data)
        afficher_record(data)
        time.sleep(DELAI_YAHOO)
    return resultats


def scraper_tout():
    """
    Scrappe toutes les catégories Yahoo Finance :
    actions US + indices + actions françaises.
    Retourne un DataFrame consolidé.
    """
    tous = []

    print("\n📈  Actions US :")
    tous += scraper_liste(TICKERS_ACTIONS, "action")

    print("\n📊  Indices :")
    tous += scraper_liste(TICKERS_INDICES, "indice")

    print("\n🇫🇷  Actions françaises :")
    tous += scraper_liste(TICKERS_FR, "action_fr")

    return pd.DataFrame(tous)


# ── Exécution autonome ────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 50)
    print("  Yahoo Finance — Collecte autonome")
    print("=" * 50)
    df = scraper_tout()
    sauvegarder(df, prefixe="yahoo")
    print(f"\n  Total : {len(df)} tickers collectés")
