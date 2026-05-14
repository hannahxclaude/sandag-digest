from __future__ import annotations
"""
County of San Diego Board of Supervisors Fetcher

The BOS has two weekly sessions:
  - Tuesday: General Legislative Session (policy, budget, intergovernmental)
  - Wednesday: Land Use Legislative Session (planning, land use — more SANDAG-relevant)

Agendas are posted by the preceding Thursday.
We fetch the BOS agenda calendar page and find the most recent posted agendas.
"""

import re
import requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from utils.pdf_extractor import extract_pdf_text

HEADERS = {"User-Agent": "SANDAG-Digest/1.0 (public records research)"}

CALENDAR_URL = "https://www.sandiegocounty.gov/content/sdc/cob/bosa.html"
AGENDA_BASE = "https://www.sandiegocounty.gov"

LOOKBACK_DAYS = 4
LOOKAHEAD_DAYS = 7


def fetch_bos_agendas(jurisdiction: dict) -> list[dict]:
    """
    Fetch the BOS agenda calendar and return text for both
    Tuesday (General) and Wednesday (Land Use) sessions
    within the date window.
    """
    try:
        resp = requests.get(CALENDAR_URL, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
    except Exception as e:
        print(f"  [BOS] Error fetching calendar: {e}")
        return []

    today = datetime.now()
    cutoff_past = today - timedelta(days=LOOKBACK_DAYS)
    cutoff_future = today + timedelta(days=LOOKAHEAD_DAYS)

    results = []

    # Find all links that look like agenda PDFs
    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = a.get_text(strip=True)
        href_lower = href.lower()
        text_lower = text.lower()

        # Must be PDF or lead to agenda
        if ".pdf" not in href_lower and "agenda" not in text_lower and "agenda" not in href_lower:
            continue

        # Skip supplemental, special, etc. for now
        if any(skip in text_lower for skip in ["supplement", "errata", "notice"]):
            continue

        # Try to find session type
        session_type = "General Legislative"
        if "land use" in text_lower or "land use" in href_lower:
            session_type = "Land Use Legislative"

        # Try to parse date
        meeting_date = _parse_bos_date(href + " " + text)
        if meeting_date and not (cutoff_past <= meeting_date <= cutoff_future):
            continue

        abs_url = href if href.startswith("http") else f"{AGENDA_BASE}{href}"
        date_str = meeting_date.strftime("%Y-%m-%d") if meeting_date else "recent"

        print(f"  [BOS] Fetching agenda: County BOS — {session_type} — {date_str}")
        text_content = extract_pdf_text(abs_url, headers=HEADERS)

        if text_content:
            results.append({
                "jurisdiction": "County of San Diego (BOS)",
                "platform": "county_bos",
                "meeting_date": date_str,
                "session_type": session_type,
                "agenda_url": abs_url,
                "text": text_content,
            })

        # Limit to 2 most recent sessions
        if len(results) >= 2:
            break

    if not results:
        print(f"  [BOS] No agendas found on calendar page — trying direct search")
        results = _try_direct_bos_fetch()

    return results


def _parse_bos_date(s: str) -> datetime | None:
    """Extract date from BOS URL or text patterns."""
    # BOS often uses patterns like /2026/05/agenda_20260513.pdf
    m = re.search(r"(20\d{2})(\d{2})(\d{2})", s)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass

    m = re.search(r"(20\d{2})[/-](\d{2})[/-](\d{2})", s)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass

    return None


def _try_direct_bos_fetch() -> list[dict]:
    """
    Fallback: try to construct a likely BOS agenda URL based on
    the most recent Tuesday/Wednesday dates.
    """
    today = datetime.now()
    results = []

    # Find most recent Tuesday and Wednesday
    for days_back in range(8):
        candidate = today - timedelta(days=days_back)
        weekday = candidate.weekday()  # 1=Tuesday, 2=Wednesday

        if weekday in (1, 2):
            session = "General Legislative" if weekday == 1 else "Land Use Legislative"
            date_str = candidate.strftime("%Y-%m-%d")

            # Try common BOS agenda URL pattern
            year = candidate.strftime("%Y")
            mmdd = candidate.strftime("%m%d")
            url = f"https://www.sandiegocounty.gov/content/dam/sdc/bos/docs/agendas/{year}/agenda_{year}{mmdd}.pdf"

            print(f"  [BOS] Trying fallback URL: {url}")
            text = extract_pdf_text(url)
            if text:
                results.append({
                    "jurisdiction": "County of San Diego (BOS)",
                    "platform": "county_bos",
                    "meeting_date": date_str,
                    "session_type": session,
                    "agenda_url": url,
                    "text": text,
                })

        if len(results) >= 2:
            break

    return results
