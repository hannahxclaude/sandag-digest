"""
Granicus Fetcher
Covers: Encinitas, San Marcos

Granicus hosts agendas at a consistent ViewPublisher URL.
We parse the meeting list HTML to find the most recent City Council meeting
and extract its agenda PDF.
"""

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
LOOKBACK_DAYS = 3
LOOKAHEAD_DAYS = 7


def fetch_granicus_agendas(jurisdiction: dict) -> list[dict]:
    """
    Scrapes the Granicus ViewPublisher page for recent/upcoming City Council
    meetings and returns agenda text.
    """
    base = jurisdiction.get("granicus_base", "")
    page_url = f"{base}/ViewPublisher.php?view_id=7"

    try:
        resp = requests.get(page_url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
    except Exception as e:
        print(f"  [Granicus] Error fetching {jurisdiction['name']}: {e}")
        return []

    results = []
    today = datetime.now()
    cutoff_past = today - timedelta(days=LOOKBACK_DAYS)
    cutoff_future = today + timedelta(days=LOOKAHEAD_DAYS)

    # Granicus tables list meetings with date and links to agenda PDF
    rows = soup.find_all("tr")
    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 2:
            continue

        row_text = row.get_text(" ", strip=True)

        # Look for City Council rows
        if "city council" not in row_text.lower():
            continue

        # Try to parse a date from the row
        date_match = re.search(r"(\w+ \d+,?\s*\d{4})", row_text)
        if not date_match:
            date_match = re.search(r"(\d{1,2}/\d{1,2}/\d{4})", row_text)
        meeting_date = None
        if date_match:
            try:
                meeting_date = datetime.strptime(
                    date_match.group(1).replace(",", ""), "%B %d %Y"
                )
            except ValueError:
                try:
                    meeting_date = datetime.strptime(date_match.group(1), "%m/%d/%Y")
                except ValueError:
                    pass

        if meeting_date and not (cutoff_past <= meeting_date <= cutoff_future):
            continue

        # Find agenda PDF link
        agenda_link = None
        for a in row.find_all("a", href=True):
            href = a["href"]
            link_text = a.get_text(strip=True).lower()
            if "agenda" in link_text or "agenda" in href.lower() or ".pdf" in href.lower():
                agenda_link = href if href.startswith("http") else f"{base}/{href.lstrip('/')}"
                break

        if not agenda_link:
            # Try MetaViewer pattern common in Granicus
            for a in row.find_all("a", href=True):
                if "MetaViewer" in a["href"] or "GeneratedAgenda" in a["href"]:
                    agenda_link = a["href"] if a["href"].startswith("http") else f"{base}/{a['href'].lstrip('/')}"
                    break

        if not agenda_link:
            continue

        date_str = meeting_date.strftime("%Y-%m-%d") if meeting_date else "unknown"
        print(f"  [Granicus] Fetching agenda: {jurisdiction['name']} — {date_str}")
        text = extract_pdf_text(agenda_link, headers=HEADERS)

        if text:
            results.append({
                "jurisdiction": jurisdiction["name"],
                "platform": "granicus",
                "meeting_date": date_str,
                "agenda_url": agenda_link,
                "text": text,
            })

    return results
