"""
Sends formatted announcement alerts to a Telegram channel via the raw
Bot API (https://api.telegram.org/bot<token>/sendMessage). Kept dependency-free
(just `requests`) since we only need one endpoint.
"""
import logging
import time
from html import escape
from typing import Dict

import requests

from classifier import BUCKET_LABEL

logger = logging.getLogger("news_bot.telegram")

API_BASE = "https://api.telegram.org/bot{token}/sendMessage"


class TelegramNotifier:
    def __init__(self, bot_token: str, channel_by_bucket: Dict[str, str]):
        self._url = API_BASE.format(token=bot_token)
        self._channel_by_bucket = channel_by_bucket

    def _format(self, record: Dict, bucket: str) -> str:
        label = BUCKET_LABEL.get(bucket, bucket)
        company = escape(record["company"] or record["symbol"])
        symbol = escape(str(record["symbol"]))
        headline = escape(record["headline"])[:600]
        exchange = record["exchange"]
        news_dt = escape(str(record["news_dt"]))

        lines = [
            f"{label} | {exchange}",
            f"<b>{company}</b> ({symbol})",
            headline,
        ]
        if record.get("pdf_url"):
            lines.append(f'🔗 <a href="{escape(record["pdf_url"])}">View filing</a>')
        lines.append(f"🕒 {news_dt}")
        return "\n".join(lines)

    def send(self, record: Dict, bucket: str, retries: int = 3) -> bool:
        channel = self._channel_by_bucket.get(bucket)
        if not channel:
            logger.warning("No Telegram channel configured for bucket %s, skipping", bucket)
            return False

        payload = {
            "chat_id": channel,
            "text": self._format(record, bucket),
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }

        for attempt in range(1, retries + 1):
            try:
                resp = requests.post(self._url, json=payload, timeout=10)
                if resp.status_code == 200:
                    return True
                if resp.status_code == 429:
                    retry_after = resp.json().get("parameters", {}).get("retry_after", 2)
                    logger.warning("Telegram rate limited, sleeping %ss", retry_after)
                    time.sleep(retry_after)
                    continue
                logger.error("Telegram send failed [%s]: %s", resp.status_code, resp.text[:300])
            except requests.RequestException as e:
                logger.warning("Telegram send attempt %s failed: %s", attempt, e)
                time.sleep(2 * attempt)
        return False
