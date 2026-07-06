"""
Central configuration, loaded from .env (see .env.example).
Keep all tunables here so main.py / sources / notifier stay clean.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


def _get(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


TELEGRAM_BOT_TOKEN = _get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHANNEL_ID = _get("TELEGRAM_CHANNEL_ID")

# Per-category overrides. Empty string -> caller falls back to TELEGRAM_CHANNEL_ID.
TELEGRAM_CHANNEL_BY_CATEGORY = {
    "RESULTS": _get("TELEGRAM_CHANNEL_RESULTS") or TELEGRAM_CHANNEL_ID,
    "CORPORATE_ACTION": _get("TELEGRAM_CHANNEL_CORP_ACTION") or TELEGRAM_CHANNEL_ID,
    "STOCK_NEWS": _get("TELEGRAM_CHANNEL_STOCK_NEWS") or TELEGRAM_CHANNEL_ID,
}

POLL_INTERVAL_SECONDS = int(_get("POLL_INTERVAL_SECONDS", "45"))

DATA_DIR = Path(_get("DEDUP_DB_PATH", "./data/seen_announcements.db")).parent
DATA_DIR.mkdir(parents=True, exist_ok=True)

DEDUP_DB_PATH = _get("DEDUP_DB_PATH", "./data/seen_announcements.db")
LOG_LEVEL = _get("LOG_LEVEL", "INFO")
LOG_FILE = _get("LOG_FILE", "./data/news_bot.log")
LIB_DOWNLOAD_FOLDER = _get("LIB_DOWNLOAD_FOLDER", "./data/cache")

Path(LIB_DOWNLOAD_FOLDER).mkdir(parents=True, exist_ok=True)


def validate() -> None:
    """Fail fast and loudly if required settings are missing."""
    missing = []
    if not TELEGRAM_BOT_TOKEN:
        missing.append("TELEGRAM_BOT_TOKEN")
    if not TELEGRAM_CHANNEL_ID and not all(TELEGRAM_CHANNEL_BY_CATEGORY.values()):
        missing.append("TELEGRAM_CHANNEL_ID (or all three per-category channel vars)")
    if missing:
        raise RuntimeError(
            "Missing required .env settings: " + ", ".join(missing) +
            "\nCopy .env.example to .env and fill these in."
        )
