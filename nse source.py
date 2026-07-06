"""
Wraps the `nse` package to fetch recent corporate announcements and
normalize them to the common record shape used across the pipeline.

NSE throttles to ~3 req/sec and is stricter about bot-like traffic than BSE,
so this source is intentionally simple (single call per poll, no pagination).
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List

from nse import NSE

logger = logging.getLogger("news_bot.nse")


def _to_record(item: Dict) -> Dict:
    return {
        "id": f"NSE:{item.get('seq_id')}",
        "exchange": "NSE",
        "company": item.get("sm_name", "").strip(),
        "symbol": item.get("symbol", ""),
        "category_raw": item.get("desc") or "",
        "subcategory_raw": "",
        "headline": item.get("attchmntText") or item.get("desc") or "",
        "pdf_url": item.get("attchmntFile") or None,
        "news_dt": item.get("an_dt") or item.get("sort_date") or "",
    }


class NseSource:
    def __init__(self, download_folder: str, server: bool = True):
        self._nse = NSE(download_folder=download_folder, server=server)

    def fetch_recent(self, lookback_minutes: int = 15) -> List[Dict]:
        now = datetime.now()
        cutoff = now - timedelta(minutes=lookback_minutes)
        try:
            rows = self._nse.announcements(index="equities", from_date=cutoff, to_date=now)
        except (TimeoutError, ConnectionError) as e:
            logger.warning("NSE fetch failed: %s", e)
            return []
        except Exception:
            logger.exception("Unexpected NSE fetch error")
            return []

        return [_to_record(r) for r in (rows or [])]

    def close(self) -> None:
        try:
            self._nse.exit()
        except Exception:
            pass
