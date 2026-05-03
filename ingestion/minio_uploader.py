"""
minio_uploader.py
─────────────────
Envoie les fichiers collectés vers MinIO (Data Lake).
Structure des buckets :
  finance-raw/       ← JSON + CSV horodatés (batch)
  finance-processed/ ← CSV latest + stream temps réel
  finance-logs/      ← fichiers de logs
"""

import os
import sys
import logging
from datetime import datetime

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

# ── Chemins ───────────────────────────────────────────────
BASE_DIR      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR      = os.path.join(BASE_DIR, "data")
RAW_DIR       = os.path.join(DATA_DIR, "raw")
PROCESSED_DIR = os.path.join(DATA_DIR, "processed")
LOGS_DIR      = os.path.join(DATA_DIR, "logs")

# ── Config MinIO ──────────────────────────────────────────
MINIO_ENDPOINT  = "http://localhost:9000"
MINIO_ACCESS    = "minioadmin"
MINIO_SECRET    = "minioadmin123"
MINIO_REGION    = "us-east-1"

BUCKET_RAW       = "finance-raw"
BUCKET_PROCESSED = "finance-processed"
BUCKET_LOGS      = "finance-logs"

# ── Logging ───────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            os.path.join(LOGS_DIR, "minio.log"),
            encoding="utf-8"
        ),
    ]
)
logger = logging.getLogger(__name__)


# ── Connexion MinIO ───────────────────────────────────────
def get_client():
    return boto3.client(
        "s3",
        endpoint_url=MINIO_ENDPOINT,
        aws_access_key_id=MINIO_ACCESS,
        aws_secret_access_key=MINIO_SECRET,
        config=Config(signature_version="s3v4"),
        region_name=MINIO_REGION,
    )


# ── Création des buckets ──────────────────────────────────
def creer_buckets(client):
    for bucket in [BUCKET_RAW, BUCKET_PROCESSED, BUCKET_LOGS]:
        try:
            client.head_bucket(Bucket=bucket)
            logger.info(f"Bucket existe deja : {bucket}")
        except ClientError:
            client.create_bucket(Bucket=bucket)
            logger.info(f"Bucket cree : {bucket}")


# ── Upload d'un fichier ───────────────────────────────────
def upload_fichier(client, chemin_local, bucket, nom_objet):
    try:
        client.upload_file(chemin_local, bucket, nom_objet)
        logger.info(f"Upload OK : {bucket}/{nom_objet}")
        return True
    except Exception as e:
        logger.error(f"Echec upload {nom_objet} : {e}")
        return False


# ── Upload de tous les fichiers locaux ────────────────────
def upload_tout():
    client = get_client()
    creer_buckets(client)

    today     = datetime.utcnow().strftime("%Y/%m/%d")
    compteur  = {"ok": 0, "erreur": 0}

    # data/raw/ → finance-raw/2026/05/03/
    for fichier in os.listdir(RAW_DIR):
        chemin = os.path.join(RAW_DIR, fichier)
        if os.path.isfile(chemin):
            nom_objet = f"{today}/{fichier}"
            if upload_fichier(client, chemin, BUCKET_RAW, nom_objet):
                compteur["ok"] += 1
            else:
                compteur["erreur"] += 1

    # data/processed/ → finance-processed/2026/05/03/
    for fichier in os.listdir(PROCESSED_DIR):
        chemin = os.path.join(PROCESSED_DIR, fichier)
        if os.path.isfile(chemin):
            nom_objet = f"{today}/{fichier}"
            if upload_fichier(client, chemin, BUCKET_PROCESSED, nom_objet):
                compteur["ok"] += 1
            else:
                compteur["erreur"] += 1

    # data/logs/ → finance-logs/2026/05/03/
    for fichier in os.listdir(LOGS_DIR):
        chemin = os.path.join(LOGS_DIR, fichier)
        if os.path.isfile(chemin):
            nom_objet = f"{today}/{fichier}"
            if upload_fichier(client, chemin, BUCKET_LOGS, nom_objet):
                compteur["ok"] += 1
            else:
                compteur["erreur"] += 1

    logger.info(f"Upload termine : {compteur['ok']} OK, {compteur['erreur']} erreurs")
    return compteur


# ── Point d'entrée ────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    from apscheduler.schedulers.blocking import BlockingScheduler

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--once",
        action="store_true",
        help="Upload unique sans scheduler"
    )
    parser.add_argument(
        "--intervalle",
        type=int,
        default=60,
        help="Intervalle en minutes (defaut: 60)"
    )
    args = parser.parse_args()

    if args.once:
        upload_tout()
    else:
        logger.info(f"Scheduler MinIO demarre - toutes les {args.intervalle} min")
        scheduler = BlockingScheduler()
        scheduler.add_job(
            upload_tout,
            trigger="interval",
            minutes=args.intervalle,
            next_run_time=datetime.now()
        )
        try:
            scheduler.start()
        except KeyboardInterrupt:
            logger.info("Scheduler MinIO arrete")   