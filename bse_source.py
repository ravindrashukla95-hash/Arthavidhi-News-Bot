"""
Wraps the `bse` package to fetch recent corporate announcements and
normalize them to the common record shape used across the pipeline.
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List

from bse import BSE

logger = logging.getLogger("news_bot.bse")

BSE_PDF_BASE = "https://www.bseindia.com/xml-data/corpfiling/AttachLive"


def _to_record(item: Dict) -> Dict:
    attachment = item.get("ATTACHMENTNAME")
    return {
        "id": f"BSE:{item.get('NEWSID')}",
        "exchange": "BSE",
        "company": item.get("SLONGNAME", "").strip(),
        "symbol": str(item.get("SCRIP_CD", "")),
        "category_raw": item.get("CATEGORYNAME") or "",
        "subcategory_raw": item.get("SUBCATNAME") or "",
        "headline": item.get("NEWSSUB") or item.get("HEADLINE") or "",
        "pdf_url": f"{BSE_PDF_BASE}/{attachment}" if attachment else None,
        "news_dt": item.get("NEWS_DT", ""),
    }


class BseSource:
    def __init__(self, download_folder: str):
        self._bse = BSE(download_folder=download_folder)

    def fetch_recent(self, lookback_minutes: int = 15, max_pages: int = 5) -> List[Dict]:
        """
        Fetch announcements from the last `lookback_minutes`.
        BSE's feed is paginated newest-first, so we stop as soon as a page's
        oldest item falls outside the window (or after max_pages, as a safety cap).
        """
        now = datetime.now()
        cutoff = now - timedelta(minutes=lookback_minutes)
        records: List[Dict] = []

        for page in range(1, max_pages + 1):
            try:
                data = self._bse.announcements(page_no=page, from_date=cutoff, to_date=now)
            except (TimeoutError, ConnectionError) as e:
                logger.warning("BSE fetch failed (page %s): %s", page, e)
                break
            except Exception:
                logger.exception("Unexpected BSE fetch error (page %s)", page)
                break

            rows = data.get("Table", [])
            if not rows:
                break

            records.extend(_to_record(r) for r in rows)

            total = 0
            if data.get("Table1"):
                total = data["Table1"][0].get("ROWCNT", 0)
            if page * len(rows) >= total:
                break

        return records

    def close(self) -> None:
        try:
            self._bse.exit()
        except Exception:
            pass
