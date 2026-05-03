"""
binance.py
───────────
Scrappe les prix temps réel depuis l'API publique Binance :
  - Prix actuel, OHLCV 24h
  - Spread bid/ask
  - Nombre de trades sur 24h
  - Volume en USD

Pas de clé API requise — 100% gratuit.

Usage autonome :
    python binance.py
"""

import time
import logging

import requests
import pandas as pd

from config import COINS_BINANCE, DELAI_BINANCE
from utils  import arrondir, en_int, maintenant, afficher_record, sauvegarder

logger = logging.getLogger(__name__)

URL_BINANCE = "https://api.binance.com/api/v3/ticker/24hr"


def scraper_tous(symboles):
    """
    Récupère les données de plusieurs paires Binance
    en UN SEUL appel API — très efficace.

    Paramètres :
        symboles : liste de paires (ex: ["BTCUSDT", "ETHUSDT"])

    Retourne :
        liste de dicts avec toutes les données
    """
    print(f"\n  📡 Binance — {len(symboles)} cryptos en 1 appel...")

    try:
        time.sleep(DELAI_BINANCE)

        # Sans paramètre = retourne TOUS les tickers Binance (~2000)
        reponse = requests.get(URL_BINANCE, timeout=15)
        reponse.raise_for_status()
        tous = reponse.json()

        # Filtrer uniquement les symboles qui nous intéressent
        symboles_set = set(symboles)
        resultats    = []

        for item in tous:
            if item["symbol"] not in symboles_set:
                continue

            # Convertir BTCUSDT → BTC-USD pour uniformiser
            ticker = item["symbol"].replace("USDT", "-USD")
            prix   = arrondir(item["lastPrice"])
            prev   = arrondir(item["prevClosePrice"])

            data = {
                "ticker":         ticker,
                "nom":            "",
                "prix":           prix,
                "ouverture":      arrondir(item["openPrice"]),
                "haut":           arrondir(item["highPrice"]),
                "bas":            arrondir(item["lowPrice"]),
                "cloture_veille": prev,
                "variation_pct":  arrondir(item["priceChangePercent"]),
                "variation_1h":   None,
                "variation_7j":   None,
                "volume":         en_int(item["quoteVolume"]),  # volume en USD
                "market_cap":     None,
                "rang":           None,
                "ath":            None,
                "supply":         None,
                "bid":            arrondir(item["bidPrice"]),   # meilleur acheteur
                "ask":            arrondir(item["askPrice"]),   # meilleur vendeur
                "nb_trades_24h":  en_int(item["count"]),
                "devise":         "USD",
                "categorie":      "crypto",
                "source":         "binance",
                "statut":         "succes",
                "collecte_le":    maintenant(),
            }
            resultats.append(data)
            afficher_record(data)

        logger.info(f"Binance — {len(resultats)} cryptos récupérées")
        return resultats

    except requests.exceptions.Timeout:
        logger.error("Binance — Timeout")
        return []
    except requests.exceptions.HTTPError as e:
        logger.error(f"Binance — Erreur HTTP : {e}")
        return []
    except Exception as e:
        logger.error(f"Binance — {e}")
        return []


def scraper_tout():
    """
    Scrappe toutes les cryptos Binance configurées.
    Retourne un DataFrame.
    """
    print("\n⚡  Cryptos temps réel (Binance) :")
    resultats = scraper_tous(COINS_BINANCE)
    return pd.DataFrame(resultats)


# ── Exécution autonome ────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 50)
    print("  Binance — Collecte autonome")
    print("=" * 50)
    df = scraper_tout()
    sauvegarder(df, prefixe="binance")
    print(f"\n  Total : {len(df)} cryptos collectées")
