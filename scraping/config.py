"""
config.py
──────────
Toute la configuration du projet en un seul endroit.
Modifie ce fichier pour ajouter/supprimer des tickers.
"""

# ── Actions US ────────────────────────────────────────────────
TICKERS_ACTIONS = [
    "AAPL",   # Apple
    "MSFT",   # Microsoft
    "NVDA",   # Nvidia
    "GOOGL",  # Google
    "AMZN",   # Amazon
    "TSLA",   # Tesla
    "META",   # Meta
]

# ── Indices boursiers ─────────────────────────────────────────
TICKERS_INDICES = [
    "^GSPC",  # S&P 500
    "^DJI",   # Dow Jones
    "^IXIC",  # NASDAQ
    "^FCHI",  # CAC 40
    "^GDAXI", # DAX
    "^FTSE",  # FTSE 100
]

# ── Actions françaises (Yahoo Finance) ────────────────────────
TICKERS_FR = [
    "TTE.PA",  # TotalEnergies
    "BN.PA",   # Danone
    "AIR.PA",  # Airbus
    "SAN.PA",  # Sanofi
    "OR.PA",   # L'Oréal
]

# ── Cryptos — IDs CoinGecko ───────────────────────────────────
COINS_COINGECKO = [
    "bitcoin",
    "ethereum",
    "binancecoin",
    "solana",
    "ripple",
    "cardano",
    "dogecoin",
    "polkadot",
]

# ── Cryptos — Symboles Binance ────────────────────────────────
COINS_BINANCE = [
    "BTCUSDT",
    "ETHUSDT",
    "BNBUSDT",
    "SOLUSDT",
    "XRPUSDT",
    "ADAUSDT",
    "DOGEUSDT",
    "DOTUSDT",
]

# ── Symboles Boursorama (CAC40) ───────────────────────────────
SYMBOLES_BOURSORAMA = [
    "1rPTTE",   # TotalEnergies
    "1rPBN",   # Danone
    "1rPAIR",  # Airbus
    "1rPSAN",  # Sanofi
]

# ── Dossier de sauvegarde ─────────────────────────────────────
DOSSIER_DATA = "data"

# ── Délais entre requêtes (secondes) ─────────────────────────
DELAI_YAHOO      = 0.5
DELAI_COINGECKO  = 2.0
DELAI_BINANCE    = 1.0
DELAI_BOURSORAMA = 3.0
