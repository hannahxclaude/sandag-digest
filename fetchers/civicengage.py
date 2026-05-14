from __future__ import annotations
"""
CivicEngage / CivicPlus Fetcher
Covers: Carlsbad, Chula Vista, Coronado, Del Mar, El Cajon, Imperial Beach,
        Lemon Grove, Poway, Santee, Vista (and Solana Beach legacy)

These sites all post agendas as PDF links on a clerk/meetings page.
We fetch the page, find the most recent agenda PDF, and extract text.
"""

import re
import requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from utils.pdf_extractor import extract_pdf_text, find_agenda_pdf_url

HEADERS = {"User-Agent": "SANDAG-Digest/1.0 (public records research)"}
LOOKBACK_DAYS = 3
LOOKAHEAD_DAYS = 7


def fetch_civicengage_agendas(jurisdiction: dict) -> list[dict]:
    """
    Fetch the agenda page, find the most recent agenda PDF link,
    extract text, and return as a list with one item.
    """
    page_url = jurisdiction["agenda_url"]

    try:
        resp = requests.get(page_url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
    except Exception as e:
        print(f"  [CivicEngage] Error fetching {jurisdiction['name']}: {e}")
        return []

    # Find all PDF links on the page
    pdf_links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = a.get_text(strip=True)
        href_lower = href.lower()
        text_lower = text.lower()

        # Must point to a PDF
        if ".pdf" not in href_lower and "pdf" not in href_lower:
            continue

        # Skip minutes, just want agendas
        if "minute" in text_lower and "agenda" not in text_lower:
            continue

        score = 0
        if "agenda" in text_lower or "agenda" in href_lower:
            score += 3
        if "packet" in text_lower or "packet" in href_lower:
            score += 2
        if "council" in text_lower or "council" in href_lower:
            score += 1

        # Prefer recent dates
        date_match = re.search(r"20(2[5-9])", href + text)
        if date_match:
            score += 2

        # Try to extract date from link text or URL
        meeting_date = _parse_date_from_text(href + " " + text)

        # Make absolute
        if href.startswith("http"):
            abs_url = href
        elif href.startswith("/"):
            from urllib.parse import urlparse
            parsed = urlparse(page_url)
            abs_url = f"{parsed.scheme}://{parsed.netloc}{href}"
        else:
            abs_url = page_url.rsplit("/", 1)[0] + "/" + href

        pdf_links.append((score, meeting_date, abs_url, text))

    if not pdf_links:
        print(f"  [CivicEngage] No agenda PDFs found on page for {jurisdiction['name']}")
        return []

    # Sort by score desc, then date desc
    pdf_links.sort(key=lambda x: (x[0], x[1] or datetime.min), reverse=True)

    # Take the top candidate
    score, meeting_date, pdf_url, link_text = pdf_links[0]

    # Filter by date window if we have a date
    if meeting_date:
        today = datetime.now()
        cutoff_past = today - timedelta(days=LOOKBACK_DAYS)
        cutoff_future = today + timedelta(days=LOOKAHEAD_DAYS)
        if not (cutoff_past <= meeting_date <= cutoff_future):
            print(f"  [CivicEngage] Best PDF outside date window for {jurisdiction['name']} ({meeting_date.date() if meeting_date else 'unknown'})")
            # Still proceed — some sites don't embed dates in URLs

    date_str = meeting_date.strftime("%Y-%m-%d") if meeting_date else "recent"
    print(f"  [CivicEngage] Fetching agenda: {jurisdiction['name']} — {date_str} — {link_text[:50]}")

    text = extract_pdf_text(pdf_url, headers=HEADERS)
    if not text:
        return []

    return [{
        "jurisdiction": jurisdiction["name"],
        "platform": "civicengage",
        "meeting_date": date_str,
        "agenda_url": pdf_url,
        "text": text,
    }]


def _parse_date_from_text(s: str) -> datetime | None:
    """Try to extract a date from a URL or link text string."""
    # Try patterns like 05-13-2025, 05132025, May 13 2025, etc.
    patterns = [
        r"(\d{2})-(\d{2})-(20\d{2})",   # MM-DD-YYYY
        r"(\d{2})\.(\d{2})\.(20\d{2})",  # MM.DD.YYYY
        r"(\d{2})(\d{2})(20\d{2})",      # MMDDYYYY
        r"(20\d{2})-(\d{2})-(\d{2})",   # YYYY-MM-DD
    ]
    for pattern in patterns:
        m = re.search(pattern, s)
        if m:
            g = m.groups()
            try:
                if len(g[0]) == 4:  # YYYY-MM-DD
                    return datetime(int(g[0]), int(g[1]), int(g[2]))
                else:
                    return datetime(int(g[2]), int(g[0]), int(g[1]))
            except ValueError:
                continue

    # Try month name patterns
    month_map = {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
        "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12
    }
    m = re.search(r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[\s\-_]*(\d{1,2})[\s\-_,]*(\d{4})", s.lower())
    if m:
        try:
            return datetime(int(m.group(3)), month_map[m.group(1)], int(m.group(2)))
        except ValueError:
            pass

    return None
