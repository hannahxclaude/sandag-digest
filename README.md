# SANDAG Agenda Digest

Monitors city council and county board meeting agendas across all 19 SANDAG member jurisdictions and flags items relevant to SANDAG's work.

## Setup

### 1. Requirements
```bash
pip install requests beautifulsoup4 lxml pdfminer.six pypdf anthropic python-dotenv
```

### 2. API Key
Create a `.env` file in this directory:
```
ANTHROPIC_API_KEY=your_key_here
```

### 3. Run it

**Full run (all 19 jurisdictions):**
```bash
python run_digest.py
```

**Test mode (3 jurisdictions: Oceanside, Encinitas, County BOS):**
```bash
python run_digest.py --test
```

**Single jurisdiction:**
```bash
python run_digest.py --jurisdiction "Oceanside"
python run_digest.py --jurisdiction "County of San Diego (BOS)"
```

Output files are saved to `./output/`:
- `digest_YYYYMMDD_HHMM.html` — email-ready HTML
- `digest_YYYYMMDD_HHMM.txt` — plain text version
- `digest_YYYYMMDD_HHMM_raw.json` — structured data for downstream use

---

## Relevance Taxonomy

The filter looks for items in these 5 categories:

| Category | What it catches |
|---|---|
| **SANDAG_DIRECT** | Any item mentioning SANDAG by name, referencing SANDAG projects or contracts |
| **TRANSPORTATION_FUNDING** | TransNet, SB 1, federal formula funds (STP/CMAQ/STBG), ATP, RAISE/BUILD grants |
| **HOUSING_RHNA** | RHNA compliance, Housing Element updates, allocation appeals |
| **ACTIVE_TRANSPORTATION** | Significant bike/ped capital projects or Complete Streets policy changes |
| **PORT_OF_ENTRY** | US-Mexico border crossings, Otay Mesa, San Ysidro, binational transportation |

---

## Platform Coverage

| Platform | Jurisdictions |
|---|---|
| Legistar | City of San Diego, Oceanside, National City |
| Granicus | Encinitas, San Marcos |
| eScribe | La Mesa |
| MuniCode | Escondido |
| CivicEngage/CivicPlus | Carlsbad, Chula Vista, Coronado, Del Mar, El Cajon, Imperial Beach, Lemon Grove, Poway, Santee, Vista |
| Legacy/Custom | Solana Beach |
| Custom | County of San Diego (BOS) |

---

## Scheduling (recommended)

Run on a **rolling daily basis** (e.g., 8am every weekday) so you catch agendas as they're posted throughout the week. The fetchers look at a ±7 day window so nothing falls through.

Add to cron:
```
0 8 * * 1-5 cd /path/to/sandag-digest && python run_digest.py --no-preview >> logs/digest.log 2>&1
```

---

## Email Delivery (optional)

To send the digest by email, add after `run()` in `run_digest.py`:

```python
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

def send_digest(digest, recipients):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = digest["subject"]
    msg["From"] = "sandag-digest@yourdomain.com"
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(digest["plain_text"], "plain"))
    msg.attach(MIMEText(digest["html"], "html"))
    
    with smtplib.SMTP("smtp.yourdomain.com", 587) as server:
        server.starttls()
        server.login(os.environ["SMTP_USER"], os.environ["SMTP_PASS"])
        server.sendmail(msg["From"], recipients, msg.as_string())
```

Or integrate with SendGrid, Mailchimp, or whatever your team uses.

---

## Maintenance Notes

- **Coronado** migrated to new agenda software May 2025 — verify URL still works
- **Solana Beach** uses a legacy CivicPlus URL with embedded params — fragile, monitor
- **County BOS** has two sessions per week; the Wednesday Land Use session is generally more SANDAG-relevant
- Legistar's web API may require a client token for some endpoints — the fetcher falls back to direct HTML scraping if the API returns 403
- City clerk pages occasionally change URLs; if a jurisdiction stops returning results, check the URL in `jurisdictions.py`
