"""
Swagit Fetcher
Covers: National City

Swagit hosts meeting videos and documents at consistent URLs.
/videos/{id}/agenda → direct PDF download (no auth required).
Meeting list is server-rendered, accessible via plain requests.
"""

from __future__ import annotations

import re
import requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from utils.pdf_extractor import extract_pdf_text

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

LOOKBACK_DAYS = 14  # bimonthly meetings need a wider lookback window
LOOKAHEAD_DAYS = 7

MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

DATE_RE = re.compile(
    r"(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
    r"\s+(\d{1,2}),?\s+(\d{4})",
    re.IGNORECASE,
)


def fetch_swagit_agendas(jurisdiction: dict) -> list[dict]:
    base_url = jurisdiction["swagit_base"]
    views_url = jurisdiction["agenda_url"]
    name = jurisdiction["name"]

    try:
        resp = requests.get(views_url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except Exception as e:
        print(f"  [Swagit] Error fetching {name}: {e}")
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    today = datetime.now()
    cutoff_past = today - timedelta(days=LOOKBACK_DAYS)
    cutoff_future = today + timedelta(days=LOOKAHEAD_DAYS)

    results = []
    seen_dates: set[str] = set()

    agenda_links = soup.find_all("a", href=re.compile(r"/videos/\d+/agenda"))

    for a in agenda_links:
        video_id = re.search(r"/videos/(\d+)/agenda", a["href"]).group(1)
        meeting_date = _find_date_near(a)
        if not meeting_date:
            continue
        if not (cutoff_past <= meeting_date <= cutoff_future):
            continue

        # Skip very short meetings (adjournment memos, typically < 15 min)
        duration_text = _find_duration_near(a)
        if duration_text and _is_short_meeting(duration_text):
            continue

        date_str = meeting_date.strftime("%Y-%m-%d")
        if date_str in seen_dates:
            continue
        seen_dates.add(date_str)

        pdf_url = f"{base_url}/videos/{video_id}/agenda"
        print(f"  [Swagit] Fetching agenda: {name} — {date_str}")
        text = extract_pdf_text(pdf_url, headers=HEADERS)

        if text:
            results.append({
                "jurisdiction": name,
                "platform": "swagit",
                "meeting_date": date_str,
                "agenda_url": pdf_url,
                "text": text,
            })

    if not results:
        print(f"  [Swagit] No agenda PDFs found in date window for {name}")

    return results


def _find_date_near(a_tag) -> datetime | None:
    node = a_tag
    for _ in range(6):
        node = node.parent
        if not node:
            break
        m = DATE_RE.search(node.get_text(" ", strip=True))
        if m:
            try:
                month = MONTH_MAP[m.group(1)[:3].lower()]
                return datetime(int(m.group(3)), month, int(m.group(2)))
            except (ValueError, KeyError):
                pass
    return None


def _find_duration_near(a_tag) -> str | None:
    node = a_tag
    for _ in range(4):
        node = node.parent
        if not node:
            break
        text = node.get_text(" ", strip=True)
        m = re.search(r"(\d+)h\s+(\d+)m|(\d+)m\s+(\d+)s", text)
        if m:
            return m.group(0)
    return None


def _is_short_meeting(duration_text: str) -> bool:
    # Under 15 minutes = likely adjournment/ceremonial, not a substantive council meeting
    h_m = re.match(r"(\d+)h\s+(\d+)m", duration_text)
    m_s = re.match(r"(\d+)m\s+(\d+)s", duration_text)
    if h_m:
        return False  # Has hours, definitely substantive
    if m_s:
        total_minutes = int(m_s.group(1))
        return total_minutes < 15
    return False
