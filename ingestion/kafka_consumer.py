"""
kafka_consumer.py
─────────────────
Lit les messages du topic crypto-prices depuis Kafka
et les sauvegarde dans data/processed/ en temps réel.
"""

import os
import sys
import json
import logging
import csv
from datetime import datetime

from kafka import KafkaConsumer

# ── Accès config ──────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "scraping"))
sys.path.insert(0, BASE_DIR)

KAFKA_BROKER       = "localhost:9093"
KAFKA_TOPIC_CRYPTO = "crypto-prices"
KAFKA_GROUP_ID     = "finance-consumer-group"

PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")
LOGS_DIR      = os.path.join(BASE_DIR, "data", "logs")

os.makedirs(PROCESSED_DIR, exist_ok=True)
os.makedirs(LOGS_DIR,      exist_ok=True)

# ── Logging ───────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            os.path.join(LOGS_DIR, "consumer.log"),
            encoding="utf-8"
        ),
    ]
)
logger = logging.getLogger(__name__)

# ── Fichier CSV de sortie (1 fichier par jour) ────────────
def get_csv_path():
    today = datetime.utcnow().strftime("%Y%m%d")
    return os.path.join(PROCESSED_DIR, f"stream_{today}.csv")

COLONNES = [
    "ticker", "prix", "prix_ouv", "prix_haut", "prix_bas",
    "volume", "variation_pct", "source", "categorie", "timestamp"
]

def ecrire_csv(event: dict):
    """Ajoute une ligne au CSV du jour."""
    chemin = get_csv_path()
    nouveau = not os.path.exists(chemin)
    with open(chemin, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=COLONNES)
        if nouveau:
            writer.writeheader()
        writer.writerow({col: event.get(col, "") for col in COLONNES})

# ── Alertes ───────────────────────────────────────────────
SEUIL_ALERTE = 2.0   # % de variation pour déclencher une alerte

def verifier_alerte(event: dict):
    ticker  = event.get("ticker", "")
    var     = event.get("variation_pct", 0)
    prix    = event.get("prix", 0)
    if abs(var) >= SEUIL_ALERTE:
        direction = "HAUSSE" if var > 0 else "BAISSE"
        logger.warning(
            f"[ALERTE] {ticker} {direction} {var:+.2f}% "
            f"→ prix actuel : {prix:.4f} USD"
        )

# ── Consumer principal ────────────────────────────────────
def lancer_consumer():
    logger.info(f"Connexion a Kafka {KAFKA_BROKER}")
    logger.info(f"Topic : {KAFKA_TOPIC_CRYPTO} | Groupe : {KAFKA_GROUP_ID}")

    consumer = KafkaConsumer(
        KAFKA_TOPIC_CRYPTO,
        bootstrap_servers=[KAFKA_BROKER],
        group_id=KAFKA_GROUP_ID,
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        auto_offset_reset="latest",      # commence à partir de maintenant
        enable_auto_commit=True,
        consumer_timeout_ms=-1,          # tourne indéfiniment
    )

    logger.info("Consumer demarre - en attente de messages...")
    compteur = 0

    try:
        for msg in consumer:
            event    = msg.value
            ticker   = event.get("ticker", "?")
            prix     = event.get("prix", 0)
            var      = event.get("variation_pct", 0)
            fleche   = "▲" if var >= 0 else "▼"

            compteur += 1

            # Affichage terminal
            logger.info(
                f"[#{compteur:>5}] {fleche} {ticker:<12} "
                f"{prix:>12.4f} USD  ({var:+.2f}%)"
            )

            # Sauvegarde CSV
            ecrire_csv(event)

            # Alertes
            verifier_alerte(event)

    except KeyboardInterrupt:
        logger.info("Consumer arrete par l'utilisateur")
    finally:
        consumer.close()
        logger.info(f"Total messages consommes : {compteur}")

# ── Point d'entrée ────────────────────────────────────────
if __name__ == "__main__":
    lancer_consumer()