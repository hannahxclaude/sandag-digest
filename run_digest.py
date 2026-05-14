"""
SANDAG Agenda Digest — Main Runner
===================================
Fetches agendas from all 19 jurisdictions, filters for relevance,
and outputs an email-ready digest.

Usage:
  python run_digest.py                     # Full run, all jurisdictions
  python run_digest.py --test              # Test mode: 3 jurisdictions only
  python run_digest.py --jurisdiction "Oceanside"  # Single jurisdiction

Environment variables:
  ANTHROPIC_API_KEY   (required)
  DIGEST_OUTPUT_DIR   (optional, defaults to ./output)
"""

import os
import sys
import json
import argparse
import smtplib
import ssl
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

# Load .env before any module imports so API keys are available at import time
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from jurisdictions import JURISDICTIONS, JURISDICTION_MAP
from fetchers.legistar import fetch_legistar_agendas
from fetchers.granicus import fetch_granicus_agendas
from fetchers.civicengage import fetch_civicengage_agendas
from fetchers.hyland_cloud import fetch_hyland_cloud_agendas
from fetchers.swagit import fetch_swagit_agendas
from fetchers.county_bos import fetch_bos_agendas
from utils.filter import filter_agenda_for_relevance
from utils.formatter import format_digest


FETCHERS = {
    "legistar": fetch_legistar_agendas,
    "granicus": fetch_granicus_agendas,
    "civicengage": fetch_civicengage_agendas,
    "hyland_cloud": fetch_hyland_cloud_agendas,
    "swagit": fetch_swagit_agendas,
    "legacy": fetch_civicengage_agendas,  # same logic, different URLs
    "escribemeetings": fetch_civicengage_agendas,  # generic PDF scraper fallback
    "municode": fetch_civicengage_agendas,          # generic PDF scraper fallback
    "county_bos": fetch_bos_agendas,
}

# For test mode: pick a spread across platforms
TEST_JURISDICTIONS = ["Oceanside", "Encinitas", "County of San Diego (BOS)"]


SEEN_FILE = Path(__file__).parent / "seen_agendas.json"


def load_seen() -> set:
    if SEEN_FILE.exists():
        try:
            return set(json.loads(SEEN_FILE.read_text()))
        except Exception:
            pass
    return set()


def save_seen(seen: set) -> None:
    SEEN_FILE.write_text(json.dumps(sorted(seen), indent=2))


def run(jurisdictions_to_run: list[dict], verbose: bool = True) -> dict:
    """
    Full pipeline: fetch → filter → format.
    Returns the digest dict.
    """
    run_date = datetime.now().strftime("%B %d, %Y")
    print(f"\n{'='*60}")
    print(f"SANDAG Agenda Digest — {run_date}")
    print(f"Jurisdictions: {len(jurisdictions_to_run)}")
    print(f"{'='*60}\n")

    seen = load_seen()
    print(f"Loaded seen state: {len(seen)} agenda(s) already processed\n")

    all_agendas = []

    # --- FETCH ---
    for j in jurisdictions_to_run:
        name = j["name"]
        platform = j["platform"]
        fetcher = FETCHERS.get(platform)

        if not fetcher:
            print(f"⚠️  No fetcher for platform '{platform}' ({name}) — skipping")
            continue

        print(f"📥 Fetching: {name} ({platform})")
        try:
            agendas = fetcher(j)
            if agendas:
                # Deduplicate: skip agendas whose URL we've already processed
                new_agendas = [a for a in agendas if a.get("agenda_url") not in seen]
                skipped = len(agendas) - len(new_agendas)
                if new_agendas:
                    print(f"   ✓ Got {len(new_agendas)} agenda(s)" + (f" ({skipped} already seen)" if skipped else ""))
                    all_agendas.extend(new_agendas)
                else:
                    print(f"   ○ All {len(agendas)} agenda(s) already seen")
            else:
                print(f"   ○ No agendas found in date window")
        except Exception as e:
            print(f"   ✗ Error: {e}")
            continue

    print(f"\n📋 Fetched {len(all_agendas)} new agenda(s) total\n")

    if not all_agendas:
        print("No new agendas to process.")
        return {}

    # --- FILTER ---
    print("🔍 Filtering for SANDAG-relevant items...\n")
    filtered_agendas = []
    for agenda in all_agendas:
        print(f"   Scanning: {agenda['jurisdiction']} ({agenda.get('meeting_date', '?')})")
        filtered = filter_agenda_for_relevance(agenda)
        filtered_agendas.append(filtered)
        count = len(filtered.get("relevant_items", []))
        if count > 0:
            print(f"   ✓ {count} relevant item(s) found")
        else:
            print(f"   ○ No relevant items")

    # --- FORMAT ---
    print(f"\n📝 Generating digest...")
    digest = format_digest(filtered_agendas, run_date=run_date)

    print(f"\n{'='*60}")
    print(f"DIGEST SUMMARY")
    print(f"{'='*60}")
    print(f"Total flagged items:     {digest['total_flagged']}")
    print(f"Jurisdictions with hits: {digest['jurisdictions_with_hits']}")
    print(f"Agendas scanned:         {len(filtered_agendas)}")
    print(f"{'='*60}\n")

    # --- SAVE OUTPUT ---
    output_dir = Path(os.environ.get("DIGEST_OUTPUT_DIR", "./output"))
    output_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")

    # Save HTML
    html_path = output_dir / f"digest_{timestamp}.html"
    html_path.write_text(digest["html"], encoding="utf-8")
    print(f"💾 HTML digest saved: {html_path}")

    # Save plain text
    txt_path = output_dir / f"digest_{timestamp}.txt"
    txt_path.write_text(digest["plain_text"], encoding="utf-8")
    print(f"💾 Text digest saved: {txt_path}")

    # Save raw JSON (useful for debugging / downstream processing)
    json_path = output_dir / f"digest_{timestamp}_raw.json"
    # Remove full text from JSON to keep it readable
    slim = [{k: v for k, v in a.items() if k != "text"} for a in filtered_agendas]
    json_path.write_text(json.dumps(slim, indent=2), encoding="utf-8")
    print(f"💾 Raw JSON saved: {json_path}")

    # --- UPDATE SEEN ---
    new_urls = {a["agenda_url"] for a in all_agendas if a.get("agenda_url")}
    seen.update(new_urls)
    save_seen(seen)
    print(f"📌 Updated seen_agendas.json (+{len(new_urls)} new URLs, {len(seen)} total)\n")

    # --- EMAIL ---
    if os.environ.get("GMAIL_ADDRESS") and os.environ.get("RECIPIENT_EMAIL"):
        send_email(digest, run_date)
    else:
        print("📧 Email skipped (GMAIL_ADDRESS / RECIPIENT_EMAIL not set)")

    if verbose and digest["total_flagged"] > 0:
        print(f"\n--- DIGEST PREVIEW ---\n")
        print(digest["plain_text"][:3000])
        if len(digest["plain_text"]) > 3000:
            print(f"\n[... {len(digest['plain_text']) - 3000} more characters ...]")

    return digest


def send_email(digest: dict, run_date: str) -> None:
    gmail_address = os.environ["GMAIL_ADDRESS"]
    gmail_password = os.environ["GMAIL_APP_PASSWORD"]
    recipient_raw = os.environ["RECIPIENT_EMAIL"]
    recipients = [e.strip() for e in recipient_raw.split(",")]

    total = digest["total_flagged"]
    subject = (
        f"SANDAG Agenda Digest — {run_date} — {total} item{'s' if total != 1 else ''} flagged"
        if total > 0
        else f"SANDAG Agenda Digest — {run_date} — Nothing flagged this week"
    )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = gmail_address
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(digest["plain_text"], "plain"))
    msg.attach(MIMEText(digest["html"], "html"))

    context = ssl.create_default_context()
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(gmail_address, gmail_password)
            server.sendmail(gmail_address, recipients, msg.as_string())
        print(f"📧 Email sent to {len(recipients)} recipient(s): {', '.join(recipients)}")
    except Exception as e:
        print(f"📧 Email failed: {e}")


def main():
    parser = argparse.ArgumentParser(description="SANDAG Agenda Digest")
    parser.add_argument("--test", action="store_true", help="Test mode: 3 jurisdictions only")
    parser.add_argument("--jurisdiction", type=str, help="Run for a single jurisdiction by name")
    parser.add_argument("--no-preview", action="store_true", help="Skip printing digest preview")
    args = parser.parse_args()

    # Validate API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY environment variable not set.")
        print("Add it to a .env file or export it in your shell.")
        sys.exit(1)

    # Determine which jurisdictions to run
    if args.jurisdiction:
        j = JURISDICTION_MAP.get(args.jurisdiction)
        if not j:
            print(f"Unknown jurisdiction: '{args.jurisdiction}'")
            print(f"Valid names: {list(JURISDICTION_MAP.keys())}")
            sys.exit(1)
        jurisdictions_to_run = [j]

    elif args.test:
        jurisdictions_to_run = [JURISDICTION_MAP[n] for n in TEST_JURISDICTIONS]
        print(f"🧪 TEST MODE: running {len(jurisdictions_to_run)} jurisdictions")

    else:
        jurisdictions_to_run = JURISDICTIONS

    run(jurisdictions_to_run, verbose=not args.no_preview)


if __name__ == "__main__":
    # Load .env if present
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    main()
