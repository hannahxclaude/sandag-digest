from __future__ import annotations
"""
Legistar Fetcher
Covers: City of San Diego, Oceanside, National City

Primary: Legistar public web calendar (Playwright, handles JavaScript rendering)
Fallback: Legistar OData API (used to be open; now requires token on some clients)
"""

import re
import requests
from datetime import datetime, timedelta
from utils.pdf_extractor import extract_pdf_text

LEGISTAR_API = "https://webapi.legistar.com/v1/{client}"
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
LOOKBACK_DAYS = 3
LOOKAHEAD_DAYS = 7


def fetch_legistar_agendas(jurisdiction: dict) -> list[dict]:
    client = jurisdiction["legistar_client"]
    results = _fetch_via_playwright(client, jurisdiction["name"])
    if not results:
        results = _fetch_via_api(client, jurisdiction["name"])
    return results


def _fetch_via_playwright(client: str, name: str) -> list[dict]:
    """
    Navigate the public Legistar web calendar with a headless browser,
    find agenda PDF links for meetings in the date window, and extract text.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return []

    today = datetime.now()
    cutoff_past = today - timedelta(days=LOOKBACK_DAYS)
    cutoff_future = today + timedelta(days=LOOKAHEAD_DAYS)
    results = []

    calendar_url = f"https://{client}.legistar.com/Calendar.aspx"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_extra_http_headers(HEADERS)
            page.goto(calendar_url, timeout=30000)
            page.wait_for_load_state("networkidle", timeout=20000)

            html = page.content()
            browser.close()
    except Exception as e:
        print(f"  [Legistar/Playwright] Error loading {name} calendar: {e}")
        return []

    # Find View.ashx agenda links and any direct PDF links
    agenda_links = re.findall(r'href=["\']([^"\']*(?:View\.ashx[^"\']*|\.pdf))["\']', html, re.IGNORECASE)
    # Also look for MeetingDetail links which can lead to agendas
    meeting_links = re.findall(r'href=["\']([^"\']*MeetingDetail\.aspx[^"\']*)["\']', html, re.IGNORECASE)

    # Try direct agenda links first
    for href in agenda_links:
        if "View.ashx" not in href and ".pdf" not in href.lower():
            continue
        abs_url = href if href.startswith("http") else f"https://{client}.legistar.com/{href.lstrip('/')}"

        # Try to extract date from URL
        meeting_date = _parse_legistar_date(href)
        if meeting_date and not (cutoff_past <= meeting_date <= cutoff_future):
            continue

        date_str = meeting_date.strftime("%Y-%m-%d") if meeting_date else "recent"
        print(f"  [Legistar] Fetching agenda: {name} — {date_str}")
        text = extract_pdf_text(abs_url, headers=HEADERS)
        if text:
            results.append({
                "jurisdiction": name,
                "platform": "legistar",
                "meeting_date": date_str,
                "agenda_url": abs_url,
                "text": text,
            })
            if len(results) >= 2:
                break

    return results


def _fetch_via_api(client: str, name: str) -> list[dict]:
    """
    Original API-based fetcher — works when Legistar API is open (no token required).
    """
    today = datetime.now()
    date_from = (today - timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%d")
    date_to = (today + timedelta(days=LOOKAHEAD_DAYS)).strftime("%Y-%m-%d")

    url = f"{LEGISTAR_API.format(client=client)}/events"
    params = {
        "$filter": (
            f"EventDate ge datetime'{date_from}' and "
            f"EventDate le datetime'{date_to}' and "
            f"EventBodyName eq 'City Council'"
        ),
        "$orderby": "EventDate desc",
        "$top": 10,
    }

    try:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        events = resp.json()
    except Exception as e:
        print(f"  [Legistar] Error fetching events for {name}: {e}")
        return []

    results = []
    for event in events:
        event_id = event.get("EventId")
        event_date = event.get("EventDate", "")[:10]
        agenda_url = event.get("EventAgendaFile")

        if not agenda_url:
            guid = event.get("EventGuid", "")
            if guid:
                agenda_url = (
                    f"https://{client}.legistar.com/View.ashx"
                    f"?M=A&ID={event_id}&GUID={guid}"
                )

        if not agenda_url:
            continue

        print(f"  [Legistar] Fetching agenda: {name} — {event_date}")
        text = extract_pdf_text(agenda_url, headers=HEADERS)
        if text:
            results.append({
                "jurisdiction": name,
                "platform": "legistar",
                "meeting_date": event_date,
                "agenda_url": agenda_url,
                "text": text,
            })

    return results


def _parse_legistar_date(s: str) -> datetime | None:
    m = re.search(r"(20\d{2})(\d{2})(\d{2})", s)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    return None
