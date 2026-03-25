# config_bot/__init__.py
"""
Configuration package exports
"""

# Import everything from credit_costs
from .credit_costs import CREDIT_COSTS, PER_CARD_COST

# Import everything from the main config file
# You need to import the actual config variables here
import os
from pathlib import Path

# Re-export all config variables
BOT_TOKEN = os.getenv("BOT_TOKEN", "7836883668:AAHAYZ4em-P3yK6cYLS7VeARVAcq71eCHUI")
ALLOWED_GROUP = int(os.getenv("ALLOWED_GROUP", "-1002962582903"))
OWNER_ID = int(os.getenv("OWNER_ID", "7622959338"))
PROXY_FILE = str(Path(__file__).parent.parent / "proxies.json")
USER_FILE = str(Path(__file__).parent.parent / "users.json")
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://blury:blury@cluster0.ahtbs9q.mongodb.net/?appName=Cluster0")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "xman_bot")
MAX_CONCURRENT_CHARGES = int(os.getenv("MAX_CONCURRENT_CHARGES", "5"))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "25"))
CONNECT_TIMEOUT = int(os.getenv("CONNECT_TIMEOUT", "8"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
HEADERS = {
    "accept": "application/json",
    "content-type": "application/x-www-form-urlencoded",
    "origin": "https://checkout.stripe.com",
    "referer": "https://checkout.stripe.com/",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "accept-language": "en-US,en;q=0.9",
}
CURRENCY_SYMBOLS = {
    "USD": "$", "EUR": "€", "GBP": "£", "INR": "₹", "JPY": "¥",
    "CNY": "¥", "KRW": "₩", "RUB": "₽", "BRL": "R$", "CAD": "C$",
    "AUD": "A$", "MXN": "MX$", "SGD": "S$", "HKD": "HK$", "THB": "฿",
    "VND": "₫", "PHP": "₱", "IDR": "Rp", "MYR": "RM", "ZAR": "R",
    "CHF": "CHF", "SEK": "kr", "NOK": "kr", "DKK": "kr", "PLN": "zł",
    "TRY": "₺", "AED": "د.إ", "SAR": "﷼", "ILS": "₪", "TWD": "NT$"
}
STRIPE_PK_KEY = os.getenv("STRIPE_PK_KEY", "pk_live_4kM0zYmj8RdKCEz9oaVNLhvl00GpRole3Q")
STRIPE_BASE_URL = os.getenv("STRIPE_BASE_URL", "https://www.propski.co.uk/")
BIN_API_URL = os.getenv("BIN_API_URL", "https://bins.antipublic.cc/bins/")
DEBUG = os.getenv("DEBUG", "False").lower() == "true"
RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "True").lower() == "true"
RATE_LIMIT = int(os.getenv("RATE_LIMIT", "5"))
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "60"))
BYPASS_METHODS = {
    "return_url": "return_url",
    "payment_intent": "payment_intent",
    "setup_future": "setup_future_usage",
    "off_session": "off_session",
    "manual": "manual",
    "incremental": "incremental"
}

# Define Config class if needed
class Config:
    """Configuration class"""
    BOT_TOKEN = BOT_TOKEN
    ALLOWED_GROUP = ALLOWED_GROUP
    OWNER_ID = OWNER_ID
    PROXY_FILE = PROXY_FILE
    USER_FILE = USER_FILE
    MONGO_URI = MONGO_URI
    MONGO_DB_NAME = MONGO_DB_NAME
    MAX_CONCURRENT_CHARGES = MAX_CONCURRENT_CHARGES
    REQUEST_TIMEOUT = REQUEST_TIMEOUT
    CONNECT_TIMEOUT = CONNECT_TIMEOUT
    MAX_RETRIES = MAX_RETRIES
    HEADERS = HEADERS
    CURRENCY_SYMBOLS = CURRENCY_SYMBOLS
    DEBUG = DEBUG
    RATE_LIMIT_ENABLED = RATE_LIMIT_ENABLED
    RATE_LIMIT = RATE_LIMIT
    RATE_LIMIT_WINDOW = RATE_LIMIT_WINDOW
    BYPASS_METHODS = BYPASS_METHODS
    STRIPE_PK_KEY = STRIPE_PK_KEY
    STRIPE_BASE_URL = STRIPE_BASE_URL
    BIN_API_URL = BIN_API_URL

config = Config()

def validate_config() -> bool:
    """Validate configuration settings"""
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN is not set!")
        return False
    return True

def print_config_summary():
    """Print a summary of the current configuration"""
    print("=" * 50)
    print("📋 Configuration Summary")
    print("=" * 50)
    print(f"  BOT_TOKEN:     {'SET' if BOT_TOKEN else 'NOT SET'}")
    print(f"  ALLOWED_GROUP: {ALLOWED_GROUP}")
    print(f"  OWNER_ID:      {OWNER_ID}")
    print(f"  MONGO_DB:      {MONGO_DB_NAME}")
    print(f"  DEBUG:         {DEBUG}")
    print("=" * 50)

# Export everything
__all__ = [
    'BOT_TOKEN',
    'ALLOWED_GROUP',
    'OWNER_ID',
    'PROXY_FILE',
    'USER_FILE',
    'MONGO_URI',
    'MONGO_DB_NAME',
    'MAX_CONCURRENT_CHARGES',
    'REQUEST_TIMEOUT',
    'CONNECT_TIMEOUT',
    'MAX_RETRIES',
    'HEADERS',
    'CURRENCY_SYMBOLS',
    'DEBUG',
    'RATE_LIMIT_ENABLED',
    'RATE_LIMIT',
    'RATE_LIMIT_WINDOW',
    'BYPASS_METHODS',
    'STRIPE_PK_KEY',
    'STRIPE_BASE_URL',
    'BIN_API_URL',
    'CREDIT_COSTS',
    'PER_CARD_COST',
    'config',
    'validate_config',
    'print_config_summary',
    'Config',
]