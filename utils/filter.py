"""
Relevance Filter
Uses the Anthropic API to scan agenda text and identify items
relevant to SANDAG's work.
"""

import os
import json
import anthropic

def _get_client():
    return anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

SYSTEM_PROMPT = """You are a research assistant for SANDAG (San Diego Association of Governments),
a regional transportation planning agency. Your job is to scan city council and county board meeting
agendas and identify items relevant to SANDAG's work.

Return ONLY a JSON object — no preamble, no markdown fences. The format must be exactly:
{
  "relevant_items": [
    {
      "item_number": "string or null",
      "title": "brief title of the agenda item",
      "relevance_category": "one of: SANDAG_DIRECT | TRANSPORTATION_FUNDING | HOUSING_RHNA | ACTIVE_TRANSPORTATION | PORT_OF_ENTRY",
      "summary": "1-2 sentence plain-language description of what the item is and why it's relevant",
      "relevance_explanation": "1 sentence explaining the SANDAG connection"
    }
  ],
  "total_items_scanned": number,
  "has_relevant_items": boolean
}

If there are no relevant items, return an empty relevant_items array and has_relevant_items: false.
"""

RELEVANCE_TAXONOMY = """
Flag agenda items that fall into ANY of these categories:

1. SANDAG_DIRECT — Item explicitly mentions SANDAG by name, references a SANDAG project,
   SANDAG funding, or SANDAG programs (e.g., SANDAG TransNet, 2021 Regional Plan, SANDAG contracts).

2. TRANSPORTATION_FUNDING — Items involving regional transportation funding streams:
   TransNet, federal formula funds (STP, CMAQ, STBG), SB 1 (Road Repair and Accountability Act),
   Active Transportation Program (ATP), Caltrans grants, federal RAISE/BUILD grants.

3. HOUSING_RHNA — Items related to Regional Housing Needs Assessment compliance,
   Housing Element updates, RHNA allocation appeals, or actions that could affect
   the city's RHNA numbers or regional housing planning.

4. ACTIVE_TRANSPORTATION — Bike lanes, pedestrian infrastructure, Vision Zero,
   Safe Routes to School, Complete Streets policies, active transportation plans.
   Note: Only flag if the item involves significant capital investment or policy change,
   not routine maintenance.

5. PORT_OF_ENTRY — Items related to US-Mexico border crossings, cross-border
   infrastructure, binational transportation, Otay Mesa, San Ysidro, or
   Tijuana/Baja California transportation connections.

Do NOT flag:
- Routine procurement/contracts unrelated to the above
- Personnel matters
- Local-only street repairs with no regional significance
- Parks and recreation
- General city administration
"""


def filter_agenda_for_relevance(agenda: dict) -> dict:
    """
    Takes an agenda dict with 'text' and returns the same dict
    with 'relevant_items' and 'has_relevant_items' added.
    """
    text = agenda.get("text", "")
    if not text.strip():
        return {**agenda, "relevant_items": [], "has_relevant_items": False}

    # Truncate very long agendas — Claude can handle up to ~180k tokens
    # but we cap at ~60k chars (~15k tokens) per agenda for efficiency
    truncated = text[:60000]
    if len(text) > 60000:
        truncated += "\n\n[Agenda truncated for length — items may continue]"

    prompt = f"""{RELEVANCE_TAXONOMY}

Below is the full text of a city council / board agenda from {agenda['jurisdiction']}
(meeting date: {agenda.get('meeting_date', 'unknown')}).

Scan every agenda item and flag those that match the taxonomy above.

AGENDA TEXT:
{truncated}"""

    try:
        message = _get_client().messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()

        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        result = json.loads(raw)
        return {
            **agenda,
            "relevant_items": result.get("relevant_items", []),
            "has_relevant_items": result.get("has_relevant_items", False),
            "total_items_scanned": result.get("total_items_scanned", 0),
        }

    except json.JSONDecodeError as e:
        print(f"  [Filter] JSON parse error for {agenda['jurisdiction']}: {e}")
        print(f"  Raw response: {raw[:300]}")
        return {**agenda, "relevant_items": [], "has_relevant_items": False}
    except Exception as e:
        print(f"  [Filter] API error for {agenda['jurisdiction']}: {e}")
        return {**agenda, "relevant_items": [], "has_relevant_items": False}
