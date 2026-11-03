"""
Find the people at a brand most likely to answer a LinkedIn approach.

Two Exa searches (people category + linkedin.com) produce candidates. An LLM then
classifies them using only the search text. Code enforces what must not depend on
the model: URLs come from search results, former staff and excluded roles are
dropped, and ranking is deterministic.

Failures never reach the pipeline. `ok=False` means "don't cache this as checked",
so an Exa outage can't hide a brand's contacts for a whole TTL.
"""

import asyncio
import json
import logging
import os
import re
import unicodedata
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote

from exa_py import Exa

from services.brand_facts import is_brand_facts_fresh

logger = logging.getLogger("services.linkedin_contacts")

MAX_CONTACTS = 3
EXA_RESULTS_PER_SEARCH = 10
EXA_TEXT_CHARS = 1500
EXA_TIMEOUT_SEC = 40
# get_llm sets no timeout, and one stalled call would otherwise hang the whole run.
LLM_TIMEOUT_SEC = 90
LOOKUP_MAX_CONCURRENT = 3
ROLE_KEYWORDS = "owner founder CEO managing director head of buying"

_PROFILE_RE = re.compile(
    r"^(?:https?://)?(?:[a-z]{2,3}\.)?linkedin\.com/in/([^/?#\s]+)/?(?:[?#].*)?$",
    re.IGNORECASE,
)


def _verification_llm():
    # Imported here because the agents package imports enrich, which imports this module.
    from agents.nodes.utils import get_llm_for_task

    return get_llm_for_task("contact_verify")


def normalize_profile_url(url: Optional[str]) -> Optional[str]:
    """Canonical personal-profile URL, or None for anything else (company pages, other hosts)."""
    match = _PROFILE_RE.match((url or "").strip())
    return f"https://www.linkedin.com/in/{match.group(1)}" if match else None


def build_people_search_url(brand_name: str, city: Optional[str] = None) -> str:
    keywords = f"{brand_name} {city or ''}".strip()
    return f"https://www.linkedin.com/search/results/people/?keywords={quote(keywords)}"


def _search_sync(exa: Exa, query: str, people_category: bool) -> List[Any]:
    kwargs: Dict[str, Any] = {
        "num_results": EXA_RESULTS_PER_SEARCH,
        "type": "auto",
        "contents": {"text": {"maxCharacters": EXA_TEXT_CHARS}},
    }
    if people_category:
        kwargs["category"] = "people"
    else:
        kwargs["include_domains"] = ["linkedin.com"]
    return exa.search(query, **kwargs).results


async def _search_candidates(exa: Exa, brand: Dict[str, Any]) -> Tuple[List[Dict[str, str]], bool]:
    """Merged, de-duplicated personal profiles from both searches, plus site-found ones."""
    name = brand.get("name") or brand.get("brand_name") or ""
    country = brand.get("origin_country") or brand.get("country") or ""
    if country.strip().lower() == "unknown":
        country = ""
    query = " ".join(f"{name} menswear {country} {ROLE_KEYWORDS}".split())

    outcomes = await asyncio.gather(
        *[
            asyncio.wait_for(asyncio.to_thread(_search_sync, exa, query, people), EXA_TIMEOUT_SEC)
            for people in (True, False)
        ],
        return_exceptions=True,
    )

    ok = True
    candidates: Dict[str, Dict[str, str]] = {}

    site_url = normalize_profile_url(brand.get("contact_linkedin"))
    if site_url:
        who = ", ".join(x for x in (brand.get("contact_name"), brand.get("contact_role")) if x)
        candidates[site_url] = {
            "url": site_url,
            "title": "",
            "text": f"Listed on the brand's own website as a current contact: {who or 'name not given'}",
        }

    for outcome in outcomes:
        if isinstance(outcome, BaseException):
            ok = False
            logger.warning("LinkedIn search failed for %s: %r", name, outcome)
            continue
        for result in outcome:
            url = normalize_profile_url(getattr(result, "url", ""))
            if url and url not in candidates:
                candidates[url] = {
                    "url": url,
                    "title": getattr(result, "title", "") or "",
                    "text": (getattr(result, "text", "") or "")[:EXA_TEXT_CHARS],
                }
    return list(candidates.values()), ok


_VERIFY_PROMPT = """A Portuguese suit manufacturer wants to contact decision-makers at the menswear brand "{name}" (website {website}, {country}).

Using ONLY the text of each candidate, classify every candidate. Never use outside knowledge.
- current: true only if the text shows the person CURRENTLY works at THIS brand. A past role, or a different company with a similar name, is false.
- tier:
  1 = owner, founder, co-founder, CEO, managing director, president, general manager of the brand
  2 = head of buying/purchasing/product/production/sourcing/merchandising, creative director, COO
  3 = CFO or other C-level, commercial/sales director, head tailor, store/boutique manager
  0 = anything else (HR, IT, marketing or finance staff below C-level, sales assistants, interns, students)
- evidence: a short quote from the text.

Return ONLY a JSON array, one object per candidate:
[{{"i": 1, "name": "", "role": "", "current": true, "tier": 1, "evidence": ""}}]

CANDIDATES:
{blocks}"""


def simplify_name(text: str) -> str:
    """Compare names loosely: no accents, case, punctuation, or '&' vs 'and'."""
    decomposed = unicodedata.normalize("NFKD", text or "")
    ascii_text = "".join(c for c in decomposed if not unicodedata.combining(c)).lower()
    ascii_text = ascii_text.replace("&", " and ")
    return " ".join(re.sub(r"[^a-z0-9]+", " ", ascii_text).split())


def _is_brand_named(person_name: str, brand_name: str) -> bool:
    person = simplify_name(person_name)
    return bool(person) and person == simplify_name(brand_name)


async def _verify_candidates(brand: Dict[str, Any], candidates: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    brand_name = brand.get("name") or brand.get("brand_name") or ""
    blocks = "\n\n".join(
        f"--- {i + 1} ---\nTITLE: {c['title']}\nTEXT: {c['text']}" for i, c in enumerate(candidates)
    )
    prompt = _VERIFY_PROMPT.format(
        name=brand_name,
        website=brand.get("website_url") or brand.get("url") or "unknown",
        country=brand.get("origin_country") or brand.get("country") or "unknown",
        blocks=blocks,
    )
    response = await asyncio.wait_for(
        _verification_llm().ainvoke(prompt), LLM_TIMEOUT_SEC
    )
    rows = json.loads(response.content.replace("```json", "").replace("```", "").strip())
    if not isinstance(rows, list):
        raise ValueError("verification did not return a list")

    verified = []
    for row in rows:
        index = row.get("i")
        tier = row.get("tier")
        name = (row.get("name") or "").strip()
        if not isinstance(index, int) or not 1 <= index <= len(candidates):
            continue
        if row.get("current") is not True or tier not in (1, 2, 3) or not name:
            continue
        brand_named = _is_brand_named(name, brand_name)
        verified.append({
            "name": name,
            "role": (row.get("role") or "").strip(),
            # A profile named after the brand isn't clearly a person: usable, but last.
            "tier": 3 if brand_named else tier,
            "linkedin_url": candidates[index - 1]["url"],
            "evidence": str(row.get("evidence") or "")[:300],
            "_rank": (brand_named, tier),
        })

    verified.sort(key=lambda c: c["_rank"])
    for contact in verified:
        del contact["_rank"]
    return verified[:MAX_CONTACTS]


async def find_linkedin_contacts(exa: Exa, brand: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], bool]:
    """Returns (contacts, ok). ok=False means the lookup was incomplete and should be retried later."""
    candidates, ok = await _search_candidates(exa, brand)
    if not candidates:
        return [], ok
    try:
        return await _verify_candidates(brand, candidates), ok
    except Exception as e:
        logger.warning("LinkedIn verification failed for %s: %r", brand.get("name"), e)
        return [], False


def apply_contacts_to_brand(brand: Dict[str, Any], contacts: List[Dict[str, Any]]) -> None:
    """Store contacts and mirror the top one into contact_* (CSV export, chat). Empty keeps existing."""
    brand["linkedin_contacts"] = contacts
    if contacts:
        top = contacts[0]
        brand["contact_name"] = top["name"]
        brand["contact_role"] = top.get("role") or None
        brand["contact_linkedin"] = top["linkedin_url"]


async def attach_linkedin_contacts(brands: List[Dict[str, Any]]) -> int:
    """Pipeline step: look up brands not checked recently. Returns how many lookups completed."""
    exa_key = os.environ.get("EXA_API_KEY")
    if not exa_key:
        logger.warning("No EXA_API_KEY — skipping LinkedIn contact lookup")
        return 0

    pending = [b for b in brands if not is_brand_facts_fresh(b.get("linkedin_contacts_checked_at"))]
    if not pending:
        return 0

    exa = Exa(api_key=exa_key)
    sem = asyncio.Semaphore(LOOKUP_MAX_CONCURRENT)

    async def lookup(brand: Dict[str, Any]) -> bool:
        async with sem:
            try:
                contacts, ok = await find_linkedin_contacts(exa, brand)
            except Exception as e:
                logger.warning("LinkedIn lookup failed for %s: %r", brand.get("name"), e)
                return False
        apply_contacts_to_brand(brand, contacts)
        if ok:
            brand["linkedin_contacts_checked_at"] = datetime.now(timezone.utc)
        return ok

    results = await asyncio.gather(*[lookup(b) for b in pending])
    return sum(results)
