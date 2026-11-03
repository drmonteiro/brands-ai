"""
Writes the LinkedIn approach for a lead: a short connection note, plus a longer
message for after the person accepts. A salesperson reviews and sends both;
nothing here contacts LinkedIn.
"""

import asyncio
import json
import logging
from typing import Any, Dict, Optional

from models import BrandLead
from services.linkedin_contacts import _is_brand_named

logger = logging.getLogger("services.linkedin_outreach")

# Safe limit for connection notes on free LinkedIn accounts.
CONNECTION_NOTE_MAX_CHARS = 200
LLM_TIMEOUT_SEC = 90


def _drafting_llm():
    # Imported here because the agents package imports enrich, which imports linkedin_contacts.
    from agents.nodes.utils import get_llm

    return get_llm(fast=False, temperature=0.7)


def _first_name(brand: BrandLead, contact: Optional[Dict[str, Any]]) -> Optional[str]:
    """First name to greet, or None when there's no real person's name to use."""
    name = ((contact or {}).get("name") or brand.contact_name or "").strip()
    if not name or _is_brand_named(name, brand.name):
        return None
    return name.split()[0].capitalize()


def _fit_note(text: str) -> str:
    """Cut on a word boundary. Only the fallback uses this: an LLM note over the limit is discarded."""
    text = " ".join(text.split())
    if len(text) <= CONNECTION_NOTE_MAX_CHARS:
        return text
    return text[:CONNECTION_NOTE_MAX_CHARS].rsplit(" ", 1)[0].rstrip(" ,;:-")


def fallback_drafts(brand: BrandLead, contact: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
    first = _first_name(brand, contact)
    greeting = f"Hello {first}" if first else "Hello"
    note = (
        f"{greeting}, I admire {brand.name}'s work. We are a tailoring manufacturer in "
        "Portugal, est. 1973, making own-label garments. I would be glad to connect."
    )
    if len(note) > CONNECTION_NOTE_MAX_CHARS:
        note = (
            f"{greeting}, we are a tailoring manufacturer in Portugal, est. 1973, "
            "making own-label garments. I would be glad to connect."
        )
    message = (
        f"{greeting}, thank you for connecting.\n\n"
        f"We were impressed by {brand.name}'s retail presence and product offer. "
        "I represent a tailoring manufacturer in central Portugal, established in 1973, "
        "supplying own-label garments to global brands, retail groups and independent businesses.\n\n"
        "We offer canvas fused and traditional half canvas jackets, as well as unstructured "
        "jackets, trousers, waistcoats and coats, primarily in wool blends, developed from "
        "our blocks or entirely to your direction.\n\n"
        "Would you be open to a short 15-minute call to see if there is a fit?"
    )
    return {"connection_note": _fit_note(note), "message": message}


async def generate_linkedin_drafts(brand: BrandLead, contact: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
    first = _first_name(brand, contact)
    role = (contact or {}).get("role") or brand.contact_role or "unknown"
    prompt = f"""Write a LinkedIn approach in English from Confeções Lança to a person at a menswear brand.

RECIPIENT: first name {first or "unknown (do not use a name; start with Hello)"}, role {role}
BRAND: {brand.name}, {brand.city or "unknown city"}, style {brand.brand_style or "premium menswear"}

FACTS YOU MAY USE (do not claim anything else about Lança):
- Tailoring manufacturer in central Portugal, established 1973
- Supplies own-label garments to global brands, retail groups and independent businesses
- Canvas fused and traditional half canvas jackets with a padded lapel; unstructured jackets; formal and casual trousers, waistcoats, coats, primarily in wool blends
- Works from in-house blocks or entirely to the client's direction; many UK clients

Return ONLY JSON with two keys:
"connection_note": sent with a connection request. MAXIMUM {CONNECTION_NOTE_MAX_CHARS - 20} characters. Warm, specific to the brand, no links, no selling, no price talk.
"message": sent after they accept. 60-110 words, plain text, ends by asking for a short 15-minute call. Do not invent facts about the brand."""

    try:
        response = await asyncio.wait_for(
            _drafting_llm().ainvoke(prompt), LLM_TIMEOUT_SEC
        )
        data = json.loads(response.content.replace("```json", "").replace("```", "").strip())
        note = " ".join(str(data.get("connection_note") or "").split())
        message = str(data.get("message") or "").strip()
    except Exception as e:
        logger.warning("LinkedIn draft generation failed for %s: %r", brand.name, e)
        return fallback_drafts(brand, contact)

    fallback = fallback_drafts(brand, contact)
    return {
        # Trimming could cut a sentence mid-thought, so an oversized note isn't used.
        "connection_note": note if note and len(note) <= CONNECTION_NOTE_MAX_CHARS else fallback["connection_note"],
        "message": message or fallback["message"],
    }
