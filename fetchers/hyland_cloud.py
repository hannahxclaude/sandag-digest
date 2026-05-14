"""
Hyland Cloud (OnBase) Fetcher
Covers: City of San Diego (migrated from Legistar ~2025)

The portal loads all meeting links on the main page (some inside HTML comments).
Downloading a PDF requires a two-step flow within a live browser session:
  1. POST to InvokeDownloadMeetingDocument → get JSON with document details
  2. GET ViewDocument → returns the actual PDF bytes
"""

from __future__ import annotations

import io
import json
import re
from datetime import datetime, timedelta
from urllib.parse import quote

BASE_URL = "https://sandiego.hylandcloud.com"
PORTAL_PATH = "/211agendaonlinecouncil"

LOOKBACK_DAYS = 3
LOOKAHEAD_DAYS = 7

SKIP_PATTERNS = [
    "closed_session",
    "public_comment",
    "public_facilities",
    "adjournment_memo",
    "meeting_memo",
]


def fetch_hyland_cloud_agendas(jurisdiction: dict) -> list[dict]:
    page_url = jurisdiction["agenda_url"]
    name = jurisdiction["name"]

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(f"  [HylandCloud] Playwright not installed — skipping {name}")
        return []

    today = datetime.now()
    cutoff_past = today - timedelta(days=LOOKBACK_DAYS)
    cutoff_future = today + timedelta(days=LOOKAHEAD_DAYS)
    results = []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ))
            page = context.new_page()
            page.goto(page_url, timeout=30000)
            page.wait_for_load_state("networkidle", timeout=20000)
            html = page.content()

            # PDF links are inside HTML comments — regex captures them
            hrefs = re.findall(
                r'href="(/211agendaonlinecouncil/Documents/Downloadfile/[^"]+\.pdf[^"]*)"',
                html,
                re.IGNORECASE,
            )

            seen_dates: set[str] = set()

            for href in hrefs:
                href_lower = href.lower()

                if "documenttype=1" not in href_lower:
                    continue

                filename_m = re.search(r"/Downloadfile/([^?]+\.pdf)", href, re.IGNORECASE)
                meetingid_m = re.search(r"meetingId=(\d+)", href, re.IGNORECASE)
                if not filename_m or not meetingid_m:
                    continue

                filename = filename_m.group(1)
                meeting_id = meetingid_m.group(1)

                if any(skip in filename.lower() for skip in SKIP_PATTERNS):
                    continue

                meeting_date = _parse_date_from_filename(filename)
                if not meeting_date:
                    continue
                if not (cutoff_past <= meeting_date <= cutoff_future):
                    continue

                date_str = meeting_date.strftime("%Y-%m-%d")
                if date_str in seen_dates:
                    continue
                seen_dates.add(date_str)

                print(f"  [HylandCloud] Fetching agenda: {name} — {date_str}")
                text = _download_pdf(context, filename, meeting_id)

                if text:
                    results.append({
                        "jurisdiction": name,
                        "platform": "hyland_cloud",
                        "meeting_date": date_str,
                        "agenda_url": (BASE_URL + href).replace("&amp;", "&"),
                        "text": text,
                    })

            browser.close()

    except Exception as e:
        print(f"  [HylandCloud] Error: {e}")

    if not results:
        print(f"  [HylandCloud] No agenda PDFs found in date window for {name}")

    return results


def _download_pdf(context, filename: str, meeting_id: str, max_chars: int = 80000) -> str:
    """POST InvokeDownloadMeetingDocument → GET ViewDocument → extract text."""
    try:
        invoke_url = (
            f"{BASE_URL}{PORTAL_PATH}/Documents/InvokeDownloadMeetingDocument/"
            f"{quote(filename)}?meetingId={meeting_id}&documentType=1"
        )
        resp1 = context.request.post(invoke_url, timeout=30000)
        data = json.loads(resp1.body())

        view_url = (
            f"{BASE_URL}{PORTAL_PATH}/Documents/ViewDocument/"
            f"{quote(data['DocumentName'])}"
            f"?meetingId={data['MeetingId']}"
            f"&documentType={data['DocumentType']}"
            f"&itemId={data.get('ItemId', 0)}"
            f"&publishId={data.get('PublishId', 0)}"
            f"&isSection={'true' if data.get('IsSection') else 'false'}"
        )
        resp2 = context.request.get(view_url, timeout=30000)
        pdf_bytes = resp2.body()

        if pdf_bytes[:4] != b"%PDF":
            return ""

        return _extract_text(pdf_bytes, max_chars)

    except Exception as e:
        print(f"  [HylandCloud] PDF download error: {e}")
        return ""


def _parse_date_from_filename(filename: str) -> datetime | None:
    m = re.search(r"_(\d{1,2})_(\d{1,2})_(20\d{2})_", filename)
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(1)), int(m.group(2)))
        except ValueError:
            pass
    return None


def _extract_text(data: bytes, max_chars: int = 80000) -> str:
    try:
        from pdfminer.high_level import extract_text_to_fp
        from pdfminer.layout import LAParams

        output = io.StringIO()
        extract_text_to_fp(
            io.BytesIO(data), output, laparams=LAParams(), output_type="text", codec="utf-8"
        )
        return output.getvalue()[:max_chars]
    except Exception:
        try:
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(data))
            return "\n".join(p.extract_text() or "" for p in reader.pages)[:max_chars]
        except Exception:
            return ""
