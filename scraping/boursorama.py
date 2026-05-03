"""
boursorama.py
──────────────
Scrappe les cours d'actions françaises depuis Boursorama :
  - Actions CAC40 et SBF120
  - Prix, OHLCV, variation
  - Données non disponibles sur Yahoo Finance

Note : Boursorama utilise Cloudflare — des blocages 403 sont
       possibles. Le script continue sans planter.

Structure réelle de l'API (vérifiée) :
    {
      "d": {
        "Name": "DANONE",
        "SymbolId": "1rPBN",
        "qv": {"d":..., "o":..., "h":..., "l":..., "c":..., "v":...},  ← veille
        "qd": {"d":..., "o":..., "h":..., "l":..., "c":..., "v":...},  ← jour
        "QuoteTab": [...]
      }
    }
    Certains symboles renvoient [] (introuvables côté Boursorama).

Usage autonome :
    python boursorama.py
"""

import time
import logging

import requests
import pandas as pd

from config import SYMBOLES_BOURSORAMA, DELAI_BOURSORAMA
from utils  import arrondir, en_int, variation_pct, maintenant, afficher_record, sauvegarder

logger = logging.getLogger(__name__)

URL_API = "https://www.boursorama.com/bourse/action/graph/ws/GetTicksEOD"

HEADERS = {
    "User-Agent":         "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36",
    "Accept":             "application/json, text/javascript, */*; q=0.01",
    "Accept-Language":    "fr-FR,fr;q=0.9,en-US;q=0.8",
    "Referer":            "https://www.boursorama.com/bourse/actions/cotations/",
    "X-Requested-With":   "XMLHttpRequest",
}


def _extraire_quote(raw, symbole):
    """
    Normalise la réponse JSON de Boursorama.

    Structure attendue :
        raw = {"d": {"Name": ..., "qd": {"o","h","l","c","v"}, "qv": {...}, ...}}

    Retourne un tuple (quote_jour, quote_veille, nom) ou lève ValueError.
    """
    # Certains symboles renvoient [] directement
    if isinstance(raw, list) or not raw:
        raise ValueError("Symbole introuvable sur Boursorama (réponse vide)")

    d = raw.get("d")

    if not d or not isinstance(d, dict):
        raise ValueError(f"Champ 'd' absent ou inattendu : {str(raw)[:200]}")

    qd  = d.get("qd", {})   # quote du jour
    qv  = d.get("qv", {})   # quote de la veille
    nom = d.get("Name", "")

    if not qd:
        raise ValueError("Champ 'qd' (quote du jour) absent dans la réponse")

    return qd, qv, nom


def scraper_symbole(symbole):
    """
    Scrappe les données d'un symbole Boursorama.

    Paramètres :
        symbole : ID Boursorama (ex: "1rPBN" pour Danone)

    Retourne :
        dict avec les données du symbole
    """
    try:
        time.sleep(DELAI_BOURSORAMA)

        params  = {"symbol": symbole, "length": 1, "period": 0, "guid": ""}
        reponse = requests.get(URL_API, params=params, headers=HEADERS, timeout=20)
        reponse.raise_for_status()
        raw     = reponse.json()

        logger.debug(f"Boursorama — {symbole} raw={str(raw)[:300]}")

        qd, qv, nom = _extraire_quote(raw, symbole)

        prix = arrondir(qd.get("c"))        # close du jour
        prev = arrondir(qv.get("c"))        # close de la veille

        return {
            "ticker":         symbole,
            "nom":            nom,
            "prix":           prix,
            "ouverture":      arrondir(qd.get("o")),
            "haut":           arrondir(qd.get("h")),
            "bas":            arrondir(qd.get("l")),
            "cloture_veille": prev,
            "variation_pct":  variation_pct(prix, prev) if prix and prev else None,
            "variation_1h":   None,
            "variation_7j":   None,
            "volume":         en_int(qd.get("v")),
            "market_cap":     None,
            "rang":           None,
            "ath":            None,
            "supply":         None,
            "bid":            None,
            "ask":            None,
            "devise":         "EUR",
            "categorie":      "action_fr",
            "source":         "boursorama",
            "statut":         "succes",
            "collecte_le":    maintenant(),
        }

    except requests.exceptions.HTTPError as e:
        msg = f"HTTP {e} — probablement bloqué par Cloudflare"
        logger.warning(f"Boursorama — {symbole} : {msg}")
        return {
            "ticker":      symbole,
            "source":      "boursorama",
            "statut":      "erreur",
            "erreur_msg":  msg,
            "collecte_le": maintenant(),
        }
    except Exception as e:
        logger.warning(f"Boursorama — {symbole} : {e}")
        return {
            "ticker":      symbole,
            "source":      "boursorama",
            "statut":      "erreur",
            "erreur_msg":  str(e),
            "collecte_le": maintenant(),
        }


def scraper_tout():
    """
    Scrappe tous les symboles Boursorama configurés.
    Retourne un DataFrame.
    """
    print("\n🏛️   Actions CAC40 (Boursorama) :")
    resultats = []
    for symbole in SYMBOLES_BOURSORAMA:
        data = scraper_symbole(symbole)
        resultats.append(data)
        afficher_record(data)
    return pd.DataFrame(resultats)


# ── Exécution autonome ────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 50)
    print("  Boursorama — Collecte autonome")
    print("=" * 50)
    df = scraper_tout()
    sauvegarder(df, prefixe="boursorama")
    print(f"\n  Total : {len(df)} actions collectées")
