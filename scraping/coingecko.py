"""
coingecko.py
─────────────
Scrappe les données crypto depuis l'API CoinGecko :
  - Prix, OHLCV 24h
  - Market cap, supply, ATH
  - Variations 1h / 24h / 7j / 30j
  - Fear & Greed Index

Usage autonome :
    python coingecko.py
"""

import time
import logging

import requests
import pandas as pd

from config import COINS_COINGECKO, DELAI_COINGECKO
from utils  import arrondir, en_int, maintenant, afficher_record, sauvegarder

logger = logging.getLogger(__name__)

URL_MARKETS    = "https://api.coingecko.com/api/v3/coins/markets"
URL_FEAR_GREED = "https://api.alternative.me/fng/?limit=1"


def scraper_markets(coin_ids):
    """
    Récupère les données de marché de plusieurs cryptos
    en UN SEUL appel API CoinGecko.

    Paramètres :
        coin_ids : liste d'IDs CoinGecko (ex: ["bitcoin", "ethereum"])

    Retourne :
        liste de dicts avec toutes les données
    """
    print(f"\n  📡 CoinGecko — {len(coin_ids)} cryptos en 1 appel...")

    params = {
        "vs_currency":             "usd",
        "ids":                     ",".join(coin_ids),
        "order":                   "market_cap_desc",
        "price_change_percentage": "1h,24h,7d,30d",
        "sparkline":               "false",
    }

    try:
        time.sleep(DELAI_COINGECKO)
        reponse = requests.get(URL_MARKETS, params=params, timeout=15)
        reponse.raise_for_status()
        donnees = reponse.json()

        resultats = []
        for coin in donnees:
            prix = coin.get("current_price")
            chg  = coin.get("price_change_24h", 0) or 0
            prev = arrondir(prix - chg) if prix else None

            data = {
                "ticker":         coin["symbol"].upper() + "-USD",
                "nom":            coin["name"],
                "prix":           prix,
                "ouverture":      None,
                "haut":           coin.get("high_24h"),
                "bas":            coin.get("low_24h"),
                "cloture_veille": prev,
                "variation_pct":  arrondir(coin.get("price_change_percentage_24h")),
                "variation_1h":   arrondir(coin.get("price_change_percentage_1h_in_currency")),
                "variation_7j":   arrondir(coin.get("price_change_percentage_7d_in_currency")),
                "volume":         en_int(coin.get("total_volume")),
                "market_cap":     en_int(coin.get("market_cap")),
                "rang":           coin.get("market_cap_rank"),
                "ath":            coin.get("ath"),
                "supply":         coin.get("circulating_supply"),
                "bid":            None,
                "ask":            None,
                "devise":         "USD",
                "categorie":      "crypto",
                "source":         "coingecko",
                "statut":         "succes",
                "collecte_le":    maintenant(),
            }
            resultats.append(data)
            afficher_record(data)

        logger.info(f"CoinGecko — {len(resultats)} cryptos récupérées")
        return resultats

    except requests.exceptions.Timeout:
        logger.error("CoinGecko — Timeout")
        return []
    except requests.exceptions.HTTPError as e:
        logger.error(f"CoinGecko — Erreur HTTP : {e}")
        return []
    except Exception as e:
        logger.error(f"CoinGecko — {e}")
        return []


def scraper_fear_and_greed():
    """
    Récupère le Fear & Greed Index.
    0 = Extreme Fear · 100 = Extreme Greed

    Retourne :
        dict {"fear_greed_valeur": int, "fear_greed_label": str}
        ou dict vide si erreur
    """
    try:
        time.sleep(1)
        reponse = requests.get(URL_FEAR_GREED, timeout=10)
        item    = reponse.json()["data"][0]
        valeur  = int(item["value"])
        label   = item["value_classification"]
        print(f"\n  😱 Fear & Greed : {valeur}/100 — {label}")
        return {"fear_greed_valeur": valeur, "fear_greed_label": label}
    except Exception as e:
        logger.warning(f"Fear & Greed — {e}")
        return {}


def scraper_tout():
    """
    Scrappe toutes les cryptos CoinGecko + Fear & Greed.
    Retourne un DataFrame.
    """
    print("\n₿   Cryptos (CoinGecko) :")
    resultats = scraper_markets(COINS_COINGECKO)
    fg        = scraper_fear_and_greed()
    return pd.DataFrame(resultats), fg


# ── Exécution autonome ────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 50)
    print("  CoinGecko — Collecte autonome")
    print("=" * 50)
    df, fg = scraper_tout()
    sauvegarder(df, prefixe="coingecko")
    print(f"\n  Total : {len(df)} cryptos collectées")
    if fg:
        print(f"  Fear & Greed : {fg['fear_greed_valeur']}/100")
