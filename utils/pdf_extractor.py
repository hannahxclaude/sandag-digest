from __future__ import annotations
"""
PDF Extractor Utility

Given a URL, either:
  - Downloads and extracts text from a PDF directly
  - Or fetches an HTML page and finds the most likely agenda PDF link, then extracts it

Uses pdfminer.six for text extraction (handles native text PDFs well).
Falls back to pypdf if needed.
"""

import io
import re
import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "SANDAG-Digest/1.0 (public records research)"}
PDF_LINK_PATTERNS = [
    r"agenda",
    r"packet",
    r"council.*meeting",
    r"regular.*meeting",
]


def extract_pdf_text(url: str, headers: dict = None, max_chars: int = 80000) -> str:
    """
    Download a PDF from `url` and return extracted text.
    Returns empty string on failure.
    """
    h = {**HEADERS, **(headers or {})}
    try:
        resp = requests.get(url, headers=h, timeout=30)
        resp.raise_for_status()

        content_type = resp.headers.get("content-type", "")
        if "pdf" in content_type or url.lower().endswith(".pdf") or _is_pdf_bytes(resp.content):
            return _extract_from_bytes(resp.content, max_chars)
        else:
            print(f"  [PDF] URL did not return a PDF: {url[:80]}")
            return ""

    except Exception as e:
        print(f"  [PDF] Error fetching {url[:80]}: {e}")
        return ""


def find_agenda_pdf_url(page_url: str, headers: dict = None) -> str | None:
    """
    Fetch an HTML page and find the most likely agenda PDF link.
    Returns the absolute URL of the best candidate, or None.
    """
    h = {**HEADERS, **(headers or {})}
    try:
        resp = requests.get(page_url, headers=h, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
    except Exception as e:
        print(f"  [PDF] Error fetching page {page_url[:80]}: {e}")
        return None

    # Collect all links
    candidates = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = a.get_text(strip=True).lower()
        href_lower = href.lower()

        # Must be a PDF
        if ".pdf" not in href_lower and "pdf" not in href_lower:
            continue

        score = 0
        for pattern in PDF_LINK_PATTERNS:
            if re.search(pattern, text) or re.search(pattern, href_lower):
                score += 1

        # Prefer links with recent dates in text or href
        import re as _re
        if _re.search(r"202[5-9]", href) or _re.search(r"202[5-9]", text):
            score += 2

        candidates.append((score, href, text))

    if not candidates:
        return None

    # Sort by score descending
    candidates.sort(key=lambda x: -x[0])
    best_href = candidates[0][1]

    # Make absolute URL
    if best_href.startswith("http"):
        return best_href
    elif best_href.startswith("/"):
        from urllib.parse import urlparse
        parsed = urlparse(page_url)
        return f"{parsed.scheme}://{parsed.netloc}{best_href}"
    else:
        return page_url.rsplit("/", 1)[0] + "/" + best_href


def _is_pdf_bytes(data: bytes) -> bool:
    """Check if bytes start with PDF magic number."""
    return data[:4] == b"%PDF"


def _extract_from_bytes(data: bytes, max_chars: int) -> str:
    """Extract text from PDF bytes using pdfminer."""
    try:
        from pdfminer.high_level import extract_text_to_fp
        from pdfminer.layout import LAParams

        output = io.StringIO()
        extract_text_to_fp(
            io.BytesIO(data),
            output,
            laparams=LAParams(),
            output_type="text",
            codec="utf-8",
        )
        text = output.getvalue()
        return text[:max_chars]

    except Exception as e:
        # Try pypdf as fallback
        try:
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(data))
            pages = [p.extract_text() or "" for p in reader.pages]
            return "\n".join(pages)[:max_chars]
        except Exception as e2:
            print(f"  [PDF] Extraction failed: {e} / {e2}")
            return ""
