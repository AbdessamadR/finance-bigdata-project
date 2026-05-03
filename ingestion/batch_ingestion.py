"""
batch_ingestion.py
──────────────────
Mode batch : appelle collecter_tout() de scraping/main.py
et déplace les fichiers dans data/raw/ et data/processed/
Planifié toutes les heures via APScheduler.
"""

import os
import sys
import shutil
import logging
from datetime import datetime

# ── Accès aux modules scraping ────────────────────────────
BASE_DIR     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRAPING_DIR = os.path.join(BASE_DIR, "scraping")
sys.path.insert(0, SCRAPING_DIR)
sys.path.insert(0, BASE_DIR)

from scraping.main   import collecter_tout
from scraping.config import DOSSIER_DATA

# ── Chemins ───────────────────────────────────────────────
RAW_DIR       = os.path.join(BASE_DIR, "data", "raw")
PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")
LOGS_DIR      = os.path.join(BASE_DIR, "data", "logs")

os.makedirs(RAW_DIR,       exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)
os.makedirs(LOGS_DIR,      exist_ok=True)

# ── Logging ───────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            os.path.join(LOGS_DIR, "batch.log"),
            encoding="utf-8"
        ),
    ]
)
logger = logging.getLogger(__name__)


# ── Réorganisation des fichiers générés ───────────────────
def reorganiser_fichiers():
    """
    Après chaque collecte, déplace :
      - *_YYYYMMDD_HHMMSS.csv  → data/raw/
      - *_YYYYMMDD_HHMMSS.json → data/raw/
      - *_latest.csv           → data/processed/
      - scraper.log            → data/logs/
    """
    data_dir = os.path.join(BASE_DIR, DOSSIER_DATA)

    for fichier in os.listdir(data_dir):
        chemin = os.path.join(data_dir, fichier)

        if not os.path.isfile(chemin):
            continue

        if fichier.endswith(".log"):
            shutil.copy2(chemin, os.path.join(LOGS_DIR, fichier))

        elif "latest" in fichier and fichier.endswith(".csv"):
            shutil.move(chemin, os.path.join(PROCESSED_DIR, fichier))

        elif fichier.endswith(".csv") or fichier.endswith(".json"):
            shutil.move(chemin, os.path.join(RAW_DIR, fichier))

    logger.info("Fichiers reorganises dans raw/ processed/ logs/")


# ── Job principal ─────────────────────────────────────────
def batch_job():
    logger.info("=" * 50)
    logger.info(f"Batch run - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 50)

    try:
        df = collecter_tout()
        reorganiser_fichiers()

        succes  = len(df[df["statut"] == "succes"])
        erreurs = len(df[df["statut"] == "erreur"])
        logger.info(f"Termine : {succes} succes, {erreurs} erreurs")

    except Exception as e:
        logger.error(f"Echec du batch : {e}", exc_info=True)


# ── Lancement ─────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    from apscheduler.schedulers.blocking import BlockingScheduler

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--once",
        action="store_true",
        help="Executer une seule fois sans scheduler"
    )
    parser.add_argument(
        "--intervalle",
        type=int,
        default=60,
        help="Intervalle en minutes (defaut: 60)"
    )
    args = parser.parse_args()

    if args.once:
        # Collecte immédiate unique
        batch_job()

    else:
        # Scheduler toutes les N minutes
        logger.info(f"Scheduler demarre - intervalle : {args.intervalle} min")
        scheduler = BlockingScheduler()
        scheduler.add_job(
            batch_job,
            trigger="interval",
            minutes=args.intervalle,
            next_run_time=datetime.now()   # exécution immédiate au démarrage
        )
        try:
            scheduler.start()
        except KeyboardInterrupt:
            logger.info("Scheduler arrete par l'utilisateur")