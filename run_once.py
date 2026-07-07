"""
Single-shot entry point for scheduled/ephemeral environments (e.g. GitHub
Actions), as opposed to main.py's continuous loop for a always-on server.

Does ONE fetch + classify + send + dedup cycle, then exits. Meant to be
invoked on a cron schedule (see .github/workflows/news-bot.yml). The dedup
SQLite file lives inside the repo checkout and the workflow commits it back
after each run, so "already seen" state survives between the fresh, throwaway
runner instances GitHub spins up for every scheduled run.
"""
import logging
import sys

import config
from bse_source import BseSource
from nse_source import NseSource
from classifier import classify
from dedup_store import DedupStore
from telegram_notifier import TelegramNotifier

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("news_bot.run_once")

# A bit wider than the ~15-min cron interval, as safety margin against
# GitHub's "best effort" scheduling delays.
LOOKBACK_MINUTES = 20


def main() -> None:
    config.validate()

    bse = BseSource(download_folder=config.LIB_DOWNLOAD_FOLDER)
    nse = NseSource(download_folder=config.LIB_DOWNLOAD_FOLDER, server=True)
    dedup = DedupStore(config.DEDUP_DB_PATH)
    telegram = TelegramNotifier(
        bot_token=config.TELEGRAM_BOT_TOKEN,
        channel_by_bucket=config.TELEGRAM_CHANNEL_BY_CATEGORY,
    )

    try:
        if dedup.count() == 0:
            logger.info("Empty dedup store — bootstrapping without sending alerts...")
            records = bse.fetch_recent(lookback_minutes=24 * 60, max_pages=10) + \
                nse.fetch_recent(lookback_minutes=24 * 60)
            for r in records:
                dedup.mark_seen(r["id"], r["exchange"], classify(r))
            logger.info("Bootstrapped %d historical announcements as already-seen.", len(records))
            return

        records = []
        try:
            records.extend(bse.fetch_recent(lookback_minutes=LOOKBACK_MINUTES))
        except Exception:
            logger.exception("BSE fetch failed")
        try:
            records.extend(nse.fetch_recent(lookback_minutes=LOOKBACK_MINUTES))
        except Exception:
            logger.exception("NSE fetch failed")

        sent = 0
        for r in records:
            if not dedup.is_new(r["id"]):
                continue
            bucket = classify(r)
            if telegram.send(r, bucket):
                dedup.mark_seen(r["id"], r["exchange"], bucket)
                sent += 1
            else:
                logger.warning("Could not deliver %s (%s)", r["id"], bucket)

        logger.info("Run complete. Sent %d new announcement(s).", sent)
    finally:
        bse.close()
        nse.close()
        dedup.close()


if __name__ == "__main__":
    main()
