"""
kafka_producer.py
─────────────────
Mode streaming : se connecte au WebSocket Binance et publie
chaque tick de prix dans un topic Kafka en temps réel.
"""

import os
import sys
import json
import logging
from datetime import datetime

import websocket
from kafka import KafkaProducer

# ── Accès config ──────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "scraping"))
sys.path.insert(0, BASE_DIR)

from config import COINS_BINANCE

KAFKA_BROKER       = "localhost:9093"
KAFKA_TOPIC_CRYPTO = "crypto-prices"
KAFKA_TOPIC_STOCKS = "stock-prices"
LOGS_DIR           = os.path.join(BASE_DIR, "data", "logs")

os.makedirs(LOGS_DIR, exist_ok=True)

# ── Logging ───────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            os.path.join(LOGS_DIR, "producer.log"),
            encoding="utf-8"
        ),
    ]
)
logger = logging.getLogger(__name__)

# ── Kafka Producer ────────────────────────────────────────
def creer_producer():
    try:
        producer = KafkaProducer(
            bootstrap_servers=[KAFKA_BROKER],
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            key_serializer=lambda k: k.encode("utf-8"),
            retries=5,
            retry_backoff_ms=1000,
        )
        logger.info(f"Producer connecte a {KAFKA_BROKER}")
        return producer
    except Exception as e:
        logger.error(f"Impossible de connecter le producer : {e}")
        raise

# ── Traitement des messages WebSocket ─────────────────────
def on_message(ws, message, producer):
    try:
        data   = json.loads(message)
        stream = data.get("stream", "")
        tick   = data.get("data", data)

        # Ignorer les messages non-ticker
        if tick.get("e") != "24hrTicker":
            return

        symbol     = tick["s"]                    # ex: BTCUSDT
        prix       = float(tick["c"])             # prix actuel
        variation  = float(tick["P"])             # variation 24h %
        volume     = float(tick["v"])             # volume 24h
        prix_haut  = float(tick["h"])             # plus haut 24h
        prix_bas   = float(tick["l"])             # plus bas 24h
        prix_ouv   = float(tick["o"])             # prix ouverture

        event = {
            "ticker":       symbol,
            "prix":         prix,
            "prix_ouv":     prix_ouv,
            "prix_haut":    prix_haut,
            "prix_bas":     prix_bas,
            "volume":       volume,
            "variation_pct": variation,
            "source":       "binance_ws",
            "categorie":    "crypto",
            "timestamp":    datetime.utcnow().isoformat(),
        }

        # Publier dans Kafka
        producer.send(
            topic=KAFKA_TOPIC_CRYPTO,
            key=symbol,
            value=event
        )
        producer.flush()

        fleche = "▲" if variation >= 0 else "▼"
        logger.info(f"{fleche} {symbol:<12} {prix:>12.4f} USD  ({variation:+.2f}%)")

    except Exception as e:
        logger.error(f"Erreur traitement message : {e}")


def on_error(ws, error):
    logger.error(f"WebSocket erreur : {error}")

def on_close(ws, close_status_code, close_msg):
    logger.warning("WebSocket ferme")

def on_open(ws):
    logger.info("WebSocket connecte a Binance")

# ── Lancement du stream ───────────────────────────────────
def lancer_stream():
    producer = creer_producer()

    # Construire l'URL multi-stream depuis COINS_BINANCE
    # COINS_BINANCE = ["BTCUSDT", "ETHUSDT", ...] → lowercase + @ticker
    streams = "/".join([
        f"{symbole.lower()}@ticker"
        for symbole in COINS_BINANCE
    ])
    url = f"wss://stream.binance.com:9443/stream?streams={streams}"
    logger.info(f"Connexion au stream : {len(COINS_BINANCE)} symboles")
    logger.info(f"URL : {url}")

    ws = websocket.WebSocketApp(
        url,
        on_open=on_open,
        on_message=lambda ws, msg: on_message(ws, msg, producer),
        on_error=on_error,
        on_close=on_close,
    )

    # Reconnexion automatique si coupure
    while True:
        try:
            ws.run_forever(ping_interval=30, ping_timeout=10)
        except KeyboardInterrupt as e:
            logger.error(f"Stream coupe, reconnexion dans 5s : {e}")
            False


# ── Point d'entrée ────────────────────────────────────────
if __name__ == "__main__":
    logger.info("Demarrage du Kafka Producer (streaming Binance)")
    lancer_stream()