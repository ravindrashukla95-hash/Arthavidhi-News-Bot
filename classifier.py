"""
Buckets a normalized announcement into one of three categories:
  RESULTS            - quarterly/annual financial results filings
  CORPORATE_ACTION   - board meetings, AGM/EGM, dividend, bonus, split, buyback,
                       book closure, allotment, postal ballot, rights issue
  STOCK_NEWS         - everything else (company updates, acquisitions, orders,
                       management changes, investor meets, ratings, etc.)

Rules are intentionally keyword-based on the fields BSE/NSE already provide
(CATEGORYNAME/SUBCATNAME for BSE, desc for NSE) with a headline-text fallback,
mirroring how the existing Google Sheet groups its BSE tab.
Tune the keyword sets below as you see misclassifications in practice.
"""
from typing import Dict

RESULTS_CATEGORY_KEYWORDS = {"result", "results"}
RESULTS_TEXT_KEYWORDS = {
    "financial result", "audited standalone", "audited consolidated",
    "unaudited financial", "quarterly result",
}

CORP_ACTION_CATEGORY_KEYWORDS = {
    "corp. action", "corp action", "corporate action",
    "board meeting", "agm/egm", "agm", "egm",
}
CORP_ACTION_TEXT_KEYWORDS = {
    "dividend", "bonus", "stock split", "buyback", "buy-back", "book closure",
    "record date", "allotment of equity shares", "postal ballot",
    "rights issue", "demerger", "scheme of arrangement", "amalgamation",
}


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def classify(record: Dict) -> str:
    """
    record must have: category_raw, subcategory_raw, headline (all str, may be empty)
    Returns one of: "RESULTS", "CORPORATE_ACTION", "STOCK_NEWS"
    """
    category = _norm(record.get("category_raw"))
    subcategory = _norm(record.get("subcategory_raw"))
    headline = _norm(record.get("headline"))
    combined_text = f"{subcategory} {headline}"

    if category in RESULTS_CATEGORY_KEYWORDS or any(k in combined_text for k in RESULTS_TEXT_KEYWORDS):
        return "RESULTS"

    if category in CORP_ACTION_CATEGORY_KEYWORDS or any(k in combined_text for k in CORP_ACTION_TEXT_KEYWORDS):
        return "CORPORATE_ACTION"

    return "STOCK_NEWS"


BUCKET_LABEL = {
    "RESULTS": "📊 RESULTS",
    "CORPORATE_ACTION": "🏛 CORPORATE ACTION",
    "STOCK_NEWS": "📰 STOCK NEWS",
}
