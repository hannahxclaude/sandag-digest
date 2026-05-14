"""
SANDAG Agenda Digest — Jurisdiction Configuration
All 19 member jurisdictions with their platform type and agenda URL.
"""

JURISDICTIONS = [
    # --- LEGISTAR (has structured API) ---
    {
        "name": "City of San Diego",
        "platform": "legistar",
        "legistar_client": "sandiego",
        "notes": "Highest volume. Meets 2x/month Mondays.",
    },
    {
        "name": "Oceanside",
        "platform": "legistar",
        "legistar_client": "oceanside",
        "notes": "Verified working. Meets 2x/month.",
    },
    {
        "name": "National City",
        "platform": "legistar",
        "legistar_client": "nationalcity",
        "notes": "High relevance — border-adjacent, transit-rich.",
    },

    # --- GRANICUS ---
    {
        "name": "Encinitas",
        "platform": "granicus",
        "agenda_url": "https://www.encinitasca.gov/government/agendas-webcasts",
        "granicus_base": "https://encinitas.granicus.com",
        "notes": "Meets 2nd/3rd/4th Wednesdays.",
    },
    {
        "name": "San Marcos",
        "platform": "civicengage",
        "agenda_url": "https://www.sanmarcosca.gov/City-Government/City-Council/Council-Meetings",
        "notes": "Meets 2x/month Tuesdays. Old Granicus URL defunct — now on sanmarcosca.gov.",
    },

    # --- ESCRIBEMEETINGS ---
    {
        "name": "La Mesa",
        "platform": "escribemeetings",
        "agenda_url": "https://pub-lamesa.escribemeetings.com/",
        "notes": "Meets 2nd & 4th Tuesdays.",
    },

    # --- MUNICODE ---
    {
        "name": "Escondido",
        "platform": "municode",
        "agenda_url": "https://escondido-ca.municodemeetings.com/",
        "notes": "Meets first 4 Wednesdays. Agendas posted Thursday before.",
    },

    # --- CIVICENGAGE / CIVICPLUS (direct PDF links on page) ---
    {
        "name": "Carlsbad",
        "platform": "civicengage",
        "agenda_url": "https://www.carlsbadca.gov/city-hall/meetings-agendas",
        "notes": "Meets ~3x/month Tuesdays.",
    },
    {
        "name": "Chula Vista",
        "platform": "civicengage",
        "agenda_url": "https://www.chulavistaca.gov/departments/mayor-council/council-meeting-agenda",
        "notes": "Meets 2x/month.",
    },
    {
        "name": "Coronado",
        "platform": "civicengage",
        "agenda_url": "https://www.coronado.ca.us/449/Agendas-Minutes",
        "notes": "Meets 1st & 3rd Tuesdays. New agenda software as of May 15, 2025.",
    },
    {
        "name": "Del Mar",
        "platform": "civicengage",
        "agenda_url": "https://www.delmar.ca.us/AgendaCenter",
        "notes": "Small city, low volume.",
    },
    {
        "name": "El Cajon",
        "platform": "civicengage",
        "agenda_url": "https://www.elcajon.gov/your-government/departments/city-clerk/public-records",
        "notes": "Meets 2x/month Tuesdays.",
    },
    {
        "name": "Imperial Beach",
        "platform": "civicengage",
        "agenda_url": "https://www.imperialbeachca.gov/129/Agendas-Minutes",
        "notes": "Meets 2x/month.",
    },
    {
        "name": "Lemon Grove",
        "platform": "civicengage",
        "agenda_url": "https://events.lemongrove.ca.gov/council",
        "notes": "Small city, low volume. Agendas on events subdomain.",
    },
    {
        "name": "Poway",
        "platform": "civicengage",
        "agenda_url": "https://poway.org/636/Council-Meetings",
        "notes": "Meets 2x/month Tuesdays.",
    },
    {
        "name": "Santee",
        "platform": "civicengage",
        "agenda_url": "https://www.cityofsanteeca.gov/departments/city-clerk/agendas-minutes",
        "notes": "Meets 2nd & 4th Wednesdays (reduced Nov-Dec).",
    },
    {
        "name": "Vista",
        "platform": "civicengage",
        "agenda_url": "https://www.cityofvista.com/city-hall/agenda-minutes",
        "notes": "Meets 2x/month Tuesdays.",
    },

    # --- LEGACY / CUSTOM ---
    {
        "name": "Solana Beach",
        "platform": "legacy",
        "agenda_url": "https://www.ci.solana-beach.ca.us/index.asp?SEC=F0F1200D-21C6-4A88-8AE1-0BC07C1A81A7&Type=B_BASIC",
        "notes": "Older CivicPlus. Fragile URL — monitor.",
    },

    # --- COUNTY BOS (custom) ---
    {
        "name": "County of San Diego (BOS)",
        "platform": "county_bos",
        "agenda_url": "https://www.sandiegocounty.gov/content/sdc/cob/bosa.html",
        "notes": "Two sessions: Tue General + Wed Land Use. Wed is more SANDAG-relevant.",
    },
]

# Lookup by name
JURISDICTION_MAP = {j["name"]: j for j in JURISDICTIONS}
