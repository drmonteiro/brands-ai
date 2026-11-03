"""
Check brands against the current quality rules using live data, without saving new
leads. Used to regenerate a city, to audit saved leads, and to measure lead quality.

Regenerating must never cost sales work or punish an outage: leads already contacted
are kept, and a technical failure says nothing about a brand, so it changes nothing.
"""

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional

from exa_py import Exa

from services.database import hide_lead, save_lead_rejections, update_lead_after_recheck
from services.lead_gate import evaluate_lead
from services.linkedin_contacts import simplify_name
from services.runtime_scoring import compute_runtime_final_score

logger = logging.getLogger("services.lead_recheck")

RECHECK_BATCH_SIZE = 12
# These only say the check itself failed.
TECHNICAL_FAILURES = frozenset({"extraction_failed", "similarity_failed", "level_unknown"})
PROTECTED_STATUSES = frozenset({"contacted", "converted"})


async def _fetch_site_text(exa: Exa, url: str) -> str:
    from agents.nodes.enrich import DISCOVERY_SLICE

    try:
        response = await asyncio.to_thread(exa.get_contents, [url], text={"maxCharacters": DISCOVERY_SLICE})
    except Exception as e:
        logger.warning("Could not read %s: %r", url, e)
        return ""
    return next((r.text for r in response.results if getattr(r, "text", None)), "")


async def assess_brands(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Real enrichment, similarity, fit and gate for brands with a known URL. One result
    per row, in order, with the decision under `_gate`. Saves nothing.
    """
    from agents.nodes import enrich as enrich_mod
    from agents.nodes import persistence as persistence_mod

    working = enrich_mod._prepare_working_brands(
        [{"url": r["url"], "brand_name": r["name"], "title": r["name"], "text": "", "highlights": ""} for r in rows]
    )
    exa = Exa(api_key=os.environ["EXA_API_KEY"])
    for brand in working:
        brand["text"] = await _fetch_site_text(exa, brand["url"])

    contents = await enrich_mod._batch_fetch_exa_supplements(working)
    assessed: List[Dict[str, Any]] = []
    for start in range(0, len(working), enrich_mod.ENRICH_BATCH_SIZE):
        batch = working[start:start + enrich_mod.ENRICH_BATCH_SIZE]
        batch_contents = contents[start:start + enrich_mod.ENRICH_BATCH_SIZE]
        extracted = await enrich_mod._extract_structured_batch(batch, batch_contents, "", "")
        for brand, row, content in zip(batch, extracted, batch_contents, strict=True):
            merged = enrich_mod._merge_extracted_into_brand(brand, row, brand)
            enrich_mod._apply_evidence(merged, row, content)
            # With nothing to read, a brand can't be judged at all.
            if not brand["text"] and not any(content.values()):
                merged["_extraction_failed"] = True
            merged["store_count"] = merged.get("_site_store_count") or 0
            assessed.append(merged)

    similar = await persistence_mod._find_similar_with_retries(
        [persistence_mod._build_profile_text(b) for b in assessed]
    )
    for start in range(0, len(assessed), persistence_mod.FIT_BATCH_SIZE):
        batch = assessed[start:start + persistence_mod.FIT_BATCH_SIZE]
        fits = await persistence_mod._llm_fit_assessment(batch, "")
        for brand, fit in zip(batch, fits, strict=True):
            brand.update(
                llm_fit_score=fit["fit_score"],
                client_level=fit["client_level"],
                closest_client=fit["closest_client"],
                llm_fit_reason=fit["fit_reason"],
            )

    for brand, matches, row in zip(assessed, similar, rows, strict=True):
        # Real clients are in the comparison table, and matching themselves proves nothing.
        others = [m for m in matches if m["name"] != row["name"]] or matches
        brand["similarity_score"] = persistence_mod._similarity_from_matches(others) if others else 0
        brand["similarity_failed"] = not others
        brand["store_count"] = brand["store_count"] or row.get("known_stores") or 1
        brand["final_score"] = compute_runtime_final_score(
            brand["similarity_score"],
            brand["llm_fit_score"],
            brand.get("avg_suit_price_eur") or 0,
            brand["store_count"],
        )[0]
        decision = evaluate_lead(brand)
        brand["_gate"] = {"accepted": decision.accepted, "code": decision.code, "reason": decision.reason}
    return assessed


def _price_note(brand: Dict[str, Any]) -> Optional[str]:
    low, high, average = (brand.get(k) for k in ("price_range_min_eur", "price_range_max_eur", "avg_suit_price_eur"))
    if low and high and low != high:
        return f"€{int(low)} - €{int(high)}"
    return f"€{int(average)}" if average else None


def fields_from_assessment(brand: Dict[str, Any]) -> Dict[str, Any]:
    """Columns to save. An unconfirmed price clears the old number, which was never proven."""
    return {
        "avg_suit_price_eur": float(brand.get("avg_suit_price_eur") or 0),
        "price_note": _price_note(brand),
        "price_status": brand.get("price_status"),
        "price_source_url": brand.get("price_source_url"),
        "price_evidence": brand.get("price_evidence") or [],
        "fit_reason": brand.get("llm_fit_reason"),
        "closest_client": brand.get("closest_client"),
        "core_category": brand.get("core_category"),
        "final_score": int(brand.get("final_score") or 0),
        "similarity_score": int(brand.get("similarity_score") or 0),
        "fit_score": int((brand.get("llm_fit_score") or 0) * 10),
    }


def _rejection(lead: Dict[str, Any], code: str, reason: str) -> Dict[str, Any]:
    return {"url": lead["website_url"], "name": lead["name"], "stage": "regeneration", "code": code, "reason": reason}


async def recheck_city_leads(city: str, leads: List[Dict[str, Any]]) -> Dict[str, int]:
    from data.lanca_clients import LANCA_CLIENTS

    summary = {"added": 0, "updated": 0, "hidden": 0, "kept_sales_work": 0, "unverified": 0}
    clients = {simplify_name(c["name"]) for c in LANCA_CLIENTS}
    clients.update(simplify_name(c.get("brand_name", "")) for c in LANCA_CLIENTS)
    clients.discard("")
    rejections: List[Dict[str, Any]] = []

    to_assess = []
    for lead in leads:
        name = simplify_name(lead["name"])
        is_client = any(client in name or name in client for client in clients)
        if is_client and lead.get("status") not in PROTECTED_STATUSES:
            await hide_lead(lead["id"])
            rejections.append(_rejection(lead, "existing_client", "Já é cliente da Lança."))
            summary["hidden"] += 1
        else:
            to_assess.append(lead)

    for start in range(0, len(to_assess), RECHECK_BATCH_SIZE):
        batch = to_assess[start:start + RECHECK_BATCH_SIZE]
        rows = [
            {
                "name": lead["name"],
                "url": lead["website_url"],
                "country": lead.get("country"),
                "known_stores": lead.get("store_count"),
            }
            for lead in batch
        ]
        try:
            assessed = await assess_brands(rows)
        except Exception as e:
            logger.exception("Recheck batch failed for %s", city)
            logger.warning("Leaving %d leads unchanged: %r", len(batch), e)
            summary["unverified"] += len(batch)
            continue

        for lead, brand in zip(batch, assessed, strict=True):
            gate = brand["_gate"]
            if gate["code"] in TECHNICAL_FAILURES:
                summary["unverified"] += 1
            elif gate["accepted"]:
                await update_lead_after_recheck(lead["id"], fields_from_assessment(brand))
                summary["updated"] += 1
            elif lead.get("status") in PROTECTED_STATUSES:
                summary["kept_sales_work"] += 1
            else:
                await hide_lead(lead["id"])
                rejections.append(_rejection(lead, gate["code"], gate["reason"]))
                summary["hidden"] += 1

    await save_lead_rejections(city, rejections)
    return summary
