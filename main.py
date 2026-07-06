"""
Arthavidhi Market News Bot
--------------------------
Polls BSE + NSE corporate announcements, classifies each into
RESULTS / CORPORATE_ACTION / STOCK_NEWS, and pushes new ones to Telegram.

Run:
    python main.py

Stop:
    Ctrl+C (graceful shutdown), or via systemd (see README.md)
"""
import logging
import signal
import sys
import time
from logging.handlers import RotatingFileHandler

import config
from bse_source import BseSource
from nse_source import NseSource
from classifier import classify
from dedup_store import DedupStore
from telegram_notifier import TelegramNotifier

logger = logging.getLogger("news_bot")


def setup_logging() -> None:
    level = getattr(logging, config.LOG_LEVEL.upper(), logging.INFO)
    handlers = [
        logging.StreamHandler(sys.stdout),
        RotatingFileHandler(config.LOG_FILE, maxBytes=5_000_000, backupCount=3),
    ]
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=handlers,
    )


def lookback_minutes() -> int:
    # Slight overlap on every poll so a slow request or clock skew
    # never lets an announcement slip through the gap between polls.
    return max(2, (config.POLL_INTERVAL_SECONDS // 60) + 2)


class Runner:
    def __init__(self):
        self.bse = BseSource(download_folder=config.LIB_DOWNLOAD_FOLDER)
        self.nse = NseSource(download_folder=config.LIB_DOWNLOAD_FOLDER, server=True)
        self.dedup = DedupStore(config.DEDUP_DB_PATH)
        self.telegram = TelegramNotifier(
            bot_token=config.TELEGRAM_BOT_TOKEN,
            channel_by_bucket=config.TELEGRAM_CHANNEL_BY_CATEGORY,
        )
        self._stop = False

    def bootstrap_if_empty(self) -> None:
        """On a brand-new dedup DB, mark today's existing announcements as
        seen WITHOUT alerting, so first launch doesn't dump a backlog into
        the channel. Only new announcements from this point on get sent."""
        if self.dedup.count() > 0:
            return
        logger.info("Empty dedup store detected — bootstrapping without sending alerts...")
        records = self.bse.fetch_recent(lookback_minutes=24 * 60, max_pages=10) + \
            self.nse.fetch_recent(lookback_minutes=24 * 60)
        for r in records:
            self.dedup.mark_seen(r["id"], r["exchange"], classify(r))
        logger.info("Bootstrapped %d historical announcements as already-seen.", len(records))

    def poll_once(self) -> None:
        window = lookback_minutes()
        records = []
        try:
            records.extend(self.bse.fetch_recent(lookback_minutes=window))
        except Exception:
            logger.exception("BSE poll failed")
        try:
            records.extend(self.nse.fetch_recent(lookback_minutes=window))
        except Exception:
            logger.exception("NSE poll failed")

        new_count = 0
        for r in records:
            if not self.dedup.is_new(r["id"]):
                continue
            bucket = classify(r)
            sent = self.telegram.send(r, bucket)
            if sent:
                self.dedup.mark_seen(r["id"], r["exchange"], bucket)
                new_count += 1
            else:
                logger.warning("Could not deliver %s (%s) — will retry next poll", r["id"], bucket)

        if new_count:
            logger.info("Sent %d new announcement(s) this cycle.", new_count)

    def run_forever(self) -> None:
        self.bootstrap_if_empty()
        logger.info("Entering poll loop (every %ss)...", config.POLL_INTERVAL_SECONDS)
        while not self._stop:
            start = time.monotonic()
            try:
                self.poll_once()
            except Exception:
                logger.exception("Unexpected error in poll cycle")
            elapsed = time.monotonic() - start
            time.sleep(max(1.0, config.POLL_INTERVAL_SECONDS - elapsed))

    def shutdown(self, *_args) -> None:
        logger.info("Shutting down...")
        self._stop = True
        self.bse.close()
        self.nse.close()
        self.dedup.close()


def main() -> None:
    setup_logging()
    config.validate()
    runner = Runner()
    signal.signal(signal.SIGINT, runner.shutdown)
    signal.signal(signal.SIGTERM, runner.shutdown)
    runner.run_forever()


if __name__ == "__main__":
    main()
