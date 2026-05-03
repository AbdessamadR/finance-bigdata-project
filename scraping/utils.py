"""
utils.py
─────────
Fonctions utilitaires partagées par tous les scrapers.
"""

import os
import logging
from datetime import datetime

import pandas as pd

from config import DOSSIER_DATA

# ── Logging ───────────────────────────────────────────────────
os.makedirs(DOSSIER_DATA, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            os.path.join(DOSSIER_DATA, "scraper.log"),
            encoding="utf-8"
        ),
    ]
)
logger = logging.getLogger(__name__)


# ── Conversions sécurisées ────────────────────────────────────

def arrondir(valeur, decimales=4):
    """Convertit en float arrondi. Retourne None si invalide."""
    try:
        return round(float(valeur), decimales)
    except (TypeError, ValueError):
        return None

def en_int(valeur):
    """Convertit en entier. Retourne None si invalide."""
    try:
        return int(float(valeur))
    except (TypeError, ValueError):
        return None

def variation_pct(prix_actuel, prix_precedent):
    """Calcule la variation en % entre deux prix."""
    try:
        if prix_precedent and prix_precedent != 0:
            return round(
                (prix_actuel - prix_precedent) / prix_precedent * 100, 2
            )
    except (TypeError, ValueError):
        pass
    return None

def maintenant():
    """Retourne la date et l'heure actuelle formatée."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ── Affichage ─────────────────────────────────────────────────

def afficher_record(data):
    """Affiche un record de manière lisible dans le terminal."""
    if data.get("statut") == "erreur":
        print(f"    ❌  {data['ticker']:<14}  ERREUR — {data.get('erreur_msg','')[:40]}")
        return

    var    = data.get("variation_pct") or 0
    fleche = "▲" if var >= 0 else "▼"
    prix   = data.get("prix") or 0
    dev    = data.get("devise", "USD")
    src    = data.get("source", "")

    print(
        f"    {fleche}  {data['ticker']:<14} "
        f"{prix:>12.2f} {dev:<4}  "
        f"({var:+.2f}%)  "
        f"[{src}]"
    )


# ── Sauvegarde ────────────────────────────────────────────────

def sauvegarder(df, prefixe="collecte"):
    """
    Sauvegarde le DataFrame en CSV + JSON.
    Crée aussi un fichier 'latest' toujours à jour.
    """
    horodatage = datetime.now().strftime("%Y%m%d_%H%M%S")

    # CSV horodaté
    chemin_csv = os.path.join(DOSSIER_DATA, f"{prefixe}_{horodatage}.csv")
    df.to_csv(chemin_csv, index=False, encoding="utf-8-sig")

    # JSON horodaté
    chemin_json = os.path.join(DOSSIER_DATA, f"{prefixe}_{horodatage}.json")
    df.to_json(chemin_json, orient="records", force_ascii=False, indent=2)

    # Fichier latest — toujours écrasé
    chemin_latest = os.path.join(DOSSIER_DATA, f"{prefixe}_latest.csv")
    df.to_csv(chemin_latest, index=False, encoding="utf-8-sig")

    print(f"\n  💾 CSV    : {chemin_csv}")
    print(f"  💾 JSON   : {chemin_json}")
    print(f"  💾 Latest : {chemin_latest}")

    return chemin_csv
