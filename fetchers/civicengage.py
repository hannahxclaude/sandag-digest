from __future__ import annotations
"""
CivicEngage / CivicPlus Fetcher
Covers: Carlsbad, Chula Vista, Coronado, Del Mar, El Cajon, Imperial Beach,
        Lemon Grove, Poway, San Marcos, Santee, Vista (and Solana Beach legacy)

Strategy:
1. Try requests with a browser User-Agent
2. If blocked (403) or no PDFs found, fall back to Playwright
"""

import re
import warnings
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
LOOKBACK_DAYS = 3
LOOKAHEAD_DAYS = 7


def fetch_civicengage_agendas(jurisdiction: dict) -> list[dict]:
    page_url = jurisdiction["agenda_url"]
    name = jurisdiction["name"]

    # Try requests first
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            resp = requests.get(page_url, headers=HEADERS, timeout=15, verify=False)
        if resp.status_code == 200:
            result = _parse_pdf_links(resp.text, page_url, name)
            if result:
                return result
            # Page loaded but no PDFs found — try Playwright in case JS renders them
    except Exception as e:
        if "403" not in str(e) and "404" not in str(e):
            print(f"  [CivicEngage] Error fetching {name}: {e}")

    # Playwright fallback
    return _fetch_via_playwright(page_url, name)


def _parse_pdf_links(html: str, page_url: str, name: str) -> list[dict]:
    """Parse PDF agenda links from HTML. Returns list with one item or empty."""
    from urllib.parse import urlparse
    soup = BeautifulSoup(html, "lxml")
    parsed_base = urlparse(page_url)
    base = f"{parsed_base.scheme}://{parsed_base.netloc}"

    pdf_links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = a.get_text(strip=True)
        href_lower = href.lower()
        text_lower = text.lower()

        if ".pdf" not in href_lower and "pdf" not in href_lower:
            continue
        if "minute" in text_lower and "agenda" not in text_lower:
            continue

        score = 0
        if "agenda" in text_lower or "agenda" in href_lower:
            score += 3
        if "packet" in text_lower or "packet" in href_lower:
            score += 2
        if "council" in text_lower or "council" in href_lower:
            score += 1
        if re.search(r"20(2[5-9])", href + text):
            score += 2

        meeting_date = _parse_date_from_text(href + " " + text)

        if href.startswith("http"):
            abs_url = href
        elif href.startswith("/"):
            abs_url = f"{base}{href}"
        else:
            abs_url = page_url.rsplit("/", 1)[0] + "/" + href

        pdf_links.append((score, meeting_date, abs_url, text))

    if not pdf_links:
        print(f"  [CivicEngage] No agenda PDFs found on page for {name}")
        return []

    pdf_links.sort(key=lambda x: (x[0], x[1] or datetime.min), reverse=True)
    score, meeting_date, pdf_url, link_text = pdf_links[0]

    if meeting_date:
        today = datetime.now()
        cutoff_past = today - timedelta(days=LOOKBACK_DAYS)
        cutoff_future = today + timedelta(days=LOOKAHEAD_DAYS)
        if not (cutoff_past <= meeting_date <= cutoff_future):
            print(f"  [CivicEngage] Best PDF outside date window for {name}")

    date_str = meeting_date.strftime("%Y-%m-%d") if meeting_date else "recent"
    print(f"  [CivicEngage] Fetching agenda: {name} — {date_str} — {link_text[:50]}")

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        text = extract_pdf_text(pdf_url, headers=HEADERS)
    if not text:
        return []

    return [{
        "jurisdiction": name,
        "platform": "civicengage",
        "meeting_date": date_str,
        "agenda_url": pdf_url,
        "text": text,
    }]


def _fetch_via_playwright(page_url: str, name: str) -> list[dict]:
    """Headless browser fallback for sites that block requests."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_extra_http_headers(HEADERS)
            page.goto(page_url, timeout=30000)
            page.wait_for_load_state("networkidle", timeout=20000)
            html = page.content()
            browser.close()
    except Exception as e:
        print(f"  [CivicEngage/Playwright] Error loading {name}: {e}")
        return []

    return _parse_pdf_links(html, page_url, name)


def _parse_date_from_text(s: str) -> datetime | None:
    patterns = [
        r"(\d{2})-(\d{2})-(20\d{2})",
        r"(\d{2})\.(\d{2})\.(20\d{2})",
        r"(\d{2})(\d{2})(20\d{2})",
        r"(20\d{2})-(\d{2})-(\d{2})",
    ]
    for pattern in patterns:
        m = re.search(pattern, s)
        if m:
            g = m.groups()
            try:
                if len(g[0]) == 4:
                    return datetime(int(g[0]), int(g[1]), int(g[2]))
                else:
                    return datetime(int(g[2]), int(g[0]), int(g[1]))
            except ValueError:
                continue

    month_map = {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
        "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12
    }
    m = re.search(
        r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[\s\-_]*(\d{1,2})[\s\-_,]*(\d{4})",
        s.lower()
    )
    if m:
        try:
            return datetime(int(m.group(3)), month_map[m.group(1)], int(m.group(2)))
        except ValueError:
            pass

    return None
