"""
Node 3: Enrich (collapsed)

Per brand:
  1. Prefill from discovery text (email regex, price/HQ/stores heuristics)
  2. Parallel Exa fetches only for still-missing fields (price + about + store-locator)
  3. Single batched LLM structured extraction (discovery + all Exa content)
  4. One batched LLM HQ knowledge fallback for brands without verified HQ
  5. Google Places + merge/validate
"""

import asyncio
import json
import logging
import os
from typing import Any, Dict, List, Optional, Union

from exa_py import Exa

from models import ProspectorState
from services.currency import extraction_fx_rules_text
from services.brand_facts import (
    apply_brand_facts_to_brand,
    get_brand_facts_batch,
    get_brand_facts_ttl_days,
    is_brand_facts_fresh,
    upsert_brand_facts_from_brands,
)
from services.database import extract_domain
from services.discovery_prefill import apply_prefill, prefill_from_discovery
from services.google_places import enrich_with_places
from services.location_enrichment import (
    EXA_MAX_CONCURRENT,
    CityContext,
    batch_check_hq_cities_against_target,
    city_in_text,
    exa_hq_lookup,
    exa_price_lookup,
    exa_store_locator_lookup,
    merge_store_data,
    resolve_headquarters_via_llm_batch,
    resolve_target_city_context,
    validate_location_data,
)
from .utils import get_llm_for_task
from .pipeline_timing import step_begin, step_end

logger = logging.getLogger("node.enrich")

ENRICH_BATCH_SIZE = 6
DISCOVERY_SLICE = 10_000
# Max concurrent unified-LLM batches (N3c); 0 = unlimited (all batches at once)
ENRICH_LLM_BATCH_CONCURRENT = int(os.environ.get("ENRICH_LLM_BATCH_CONCURRENT", "0"))


# ============================================================================
# EXA: parallel supplement (only missing fields)
# ============================================================================

def _needs_exa_price(brand: Dict) -> bool:
    return brand.get("avg_suit_price_eur") is None and brand.get("price_range_min_eur") is None


def _needs_exa_about(brand: Dict) -> bool:
    return brand.get("headquarters_confidence") != "verified"


def _needs_exa_stores(brand: Dict) -> bool:
    return brand.get("_site_store_confidence") != "verified"


async def _fetch_exa_supplement_for_brand(
    exa: Exa,
    brand: Dict,
    sem: asyncio.Semaphore,
) -> Dict[str, str]:
    """Run price/about/store Exa searches in parallel for one brand."""
    name = brand.get("name") or brand.get("brand_name") or brand.get("title", "")
    url = brand.get("website_url") or brand.get("url", "")

    async def _maybe(coro):
        return await coro

    tasks: Dict[str, Any] = {}
    if _needs_exa_price(brand):
        tasks["price"] = exa_price_lookup(exa, name, url, sem=sem)
    if _needs_exa_about(brand):
        tasks["about"] = exa_hq_lookup(exa, name, url, sem=sem)
    if _needs_exa_stores(brand):
        tasks["stores"] = exa_store_locator_lookup(exa, name, url, sem=sem)

    out = {"price": "", "about": "", "stores": ""}
    if not tasks:
        return out

    keys = list(tasks.keys())
    results = await asyncio.gather(*[tasks[k] for k in keys], return_exceptions=True)
    for key, result in zip(keys, results):
        if isinstance(result, Exception):
            logger.warning("Exa %s failed for %s: %s", key, name, result)
            out[key] = ""
        else:
            out[key] = result or ""
    return out


async def _batch_fetch_exa_supplements(brands: List[Dict]) -> List[Dict[str, str]]:
    exa_key = os.environ.get("EXA_API_KEY")
    if not exa_key:
        logger.warning("No EXA_API_KEY — skipping supplemental Exa fetches")
        return [{"price": "", "about": "", "stores": ""} for _ in brands]

    exa = Exa(api_key=exa_key)
    sem = asyncio.Semaphore(EXA_MAX_CONCURRENT)
    results = await asyncio.gather(
        *[_fetch_exa_supplement_for_brand(exa, b, sem) for b in brands]
    )
    return list(results)


# ============================================================================
# LLM: unified structured extraction (single pass per batch)
# ============================================================================

def _apply_site_store_fields(brand: Dict, extracted: Dict) -> None:
    addresses = extracted.get("site_store_addresses") or []
    if isinstance(addresses, str):
        try:
            addresses = json.loads(addresses)
        except Exception:
            addresses = [addresses] if addresses else []
    confidence = (extracted.get("site_store_confidence") or "unknown").lower()
    count = extracted.get("site_store_count")
    if confidence == "verified" and addresses:
        brand["_site_store_addresses"] = list(addresses)
        brand["_site_store_count"] = count if count is not None else len(addresses)
        brand["_site_store_confidence"] = "verified"
    elif confidence == "verified" and count:
        brand["_site_store_addresses"] = []
        brand["_site_store_count"] = int(count)
        brand["_site_store_confidence"] = "verified"
    else:
        brand.setdefault("_site_store_addresses", [])
        brand.setdefault("_site_store_count", None)
        brand.setdefault("_site_store_confidence", "unknown")


async def _extract_structured_batch(
    brands: List[Dict],
    exa_contents: List[Dict[str, str]],
    target_city: str,
    target_country: str,
) -> List[Dict]:
    """
    One LLM call per batch: discovery + pricing + about + store-locator combined.
    """
    llm = get_llm_for_task("structured_extract")
    fx_rules = extraction_fx_rules_text()

    blocks = []
    for i, b in enumerate(brands):
        exa = exa_contents[i] if i < len(exa_contents) else {}
        discovery = (b.get("text") or b.get("highlights") or "")[:DISCOVERY_SLICE]
        prefill_note = ""
        if b.get("contact_email"):
            prefill_note += f"Prefill email (regex): {b['contact_email']}\n"
        if b.get("headquarters_city") and b.get("headquarters_confidence") == "verified":
            prefill_note += f"Prefill HQ (discovery): {b['headquarters_city']} (verified)\n"
        if b.get("avg_suit_price_eur"):
            prefill_note += f"Prefill price hint: €{b['avg_suit_price_eur']}\n"

        blocks.append(
            f"=== BRAND {i + 1} ===\n"
            f"URL: {b.get('url') or b.get('website_url', '')}\n"
            f"BRAND NAME (from filter): {b.get('brand_name') or b.get('name', '')}\n"
            f"PREFILL (from discovery, trust if verified):\n{prefill_note or '(none)'}\n"
            f"DISCOVERY CONTENT:\n{discovery}\n"
            f"PRICING PAGE CONTENT:\n{(exa.get('price') or '')[:3000]}\n"
            f"ABOUT/HQ PAGE CONTENT:\n{(exa.get('about') or '')[:3000]}\n"
            f"STORE LOCATOR CONTENT:\n{(exa.get('stores') or '')[:3000]}"
        )

    prompt = f"""You are a data analyst extracting structured information about menswear brands for a Portuguese suit manufacturer (Confeções Lança).

CITY: {target_city}
COUNTRY: {target_country}

For each brand, use ALL content sections below (discovery + pricing + about + store locator).
If information is not available, use null.

BRANDS ({len(brands)} total):
{chr(10).join(blocks)}

TASK: Extract structured data for each brand.
Return ONLY a JSON array with one object per brand, in SAME order:
[{{
  "name": "Brand Name",
  "website_url": "https://...",
  "origin_country": "Country where brand is headquartered",
  "headquarters_city": "City where brand HQ is located (explicit evidence only) or null",
  "headquarters_confidence": "verified" or "unknown",
  "avg_suit_price_eur": 800,
  "price_range_min_eur": 500,
  "price_range_max_eur": 1200,
  "made_to_measure": true/false/null,
  "wool_percentage": "100%" or "mixed" or null,
  "brand_style": "Heritage/Premium/Contemporary/Luxury/Traditional",
  "business_model": "Retail/Bespoke/Multi-brand/Online+Retail",
  "company_overview": "2-3 sentences describing the brand",
  "contact_email": "email found in content or null",
  "site_store_addresses": ["full address or city strings explicitly listed"],
  "site_store_count": 5,
  "site_store_confidence": "verified" or "unknown",
  "clothing_types": ["suits", "blazers"],
  "target_gender": "men" or "unisex" or "women",
  "is_chain": true/false/null,
  "bespoke_only": true/false/null
}}]

PRICING RULES:
- PRIORITIZE prices from PRICING PAGE CONTENT
- {fx_rules}
- If only one price found, use it as both min and max; if none, null
- avg_suit_price_eur = midpoint of min and max when both exist

HEADQUARTERS RULES:
- ONLY extract HQ city if EXPLICITLY stated (based in, headquartered, registered office, footer HQ)
- NEVER guess from store locations or target city {target_city}
- If unclear: null and headquarters_confidence "unknown"
- If explicit: headquarters_confidence "verified"

STORE RULES:
- site_store_addresses: ONLY stores explicitly listed in STORE LOCATOR or discovery
- site_store_count: only if explicitly stated; else null
- site_store_confidence: "verified" only when explicit list or count in content; else "unknown"
- NEVER invent stores

EMAIL RULES:
- Prefer sales@, info@, contact@, hello@ — no noreply/personal
- Discovery prefill email is valid if present in content

Return ONLY the JSON array."""

    try:
        response = await llm.ainvoke(prompt)
        raw = response.content.replace("```json", "").replace("```", "").strip()
        results = json.loads(raw)
        if not isinstance(results, list):
            results = [results]
        for r in results:
            if not r.get("headquarters_city"):
                r["headquarters_confidence"] = "unknown"
            elif r.get("headquarters_confidence") not in ("verified", "llm_knowledge"):
                r["headquarters_confidence"] = "verified"
        return results
    except Exception as e:
        logger.warning("Unified enrich LLM error: %s — returning minimal data", e)
        return [
            {
                "name": b.get("brand_name", b.get("title", "")),
                "website_url": b.get("url", ""),
                "origin_country": None,
                "headquarters_city": b.get("headquarters_city"),
                "headquarters_confidence": b.get("headquarters_confidence", "unknown"),
                "avg_suit_price_eur": b.get("avg_suit_price_eur"),
                "price_range_min_eur": b.get("price_range_min_eur"),
                "price_range_max_eur": b.get("price_range_max_eur"),
                "made_to_measure": None,
                "wool_percentage": None,
                "brand_style": None,
                "business_model": None,
                "company_overview": None,
                "contact_email": b.get("contact_email"),
                "site_store_addresses": b.get("_site_store_addresses", []),
                "site_store_count": b.get("_site_store_count"),
                "site_store_confidence": b.get("_site_store_confidence", "unknown"),
                "clothing_types": [],
                "target_gender": None,
                "is_chain": None,
                "bespoke_only": None,
            }
            for b in brands
        ]


def _merge_extracted_into_brand(brand: Dict, extracted: Dict, source_row: Dict) -> Dict:
    """Merge LLM output; never downgrade verified discovery prefill."""
    out = dict(brand)
    url = source_row.get("url") or source_row.get("website_url", "")
    out["website_url"] = extracted.get("website_url") or url
    out["name"] = extracted.get("name") or source_row.get("brand_name") or source_row.get("title", "")

    for key in (
        "origin_country", "avg_suit_price_eur", "price_range_min_eur", "price_range_max_eur",
        "made_to_measure", "wool_percentage", "brand_style", "business_model",
        "company_overview", "clothing_types", "target_gender", "is_chain", "bespoke_only",
    ):
        val = extracted.get(key)
        if val is not None:
            out[key] = val

    if not out.get("contact_email") and extracted.get("contact_email"):
        out["contact_email"] = extracted["contact_email"]

    hq_conf_existing = brand.get("headquarters_confidence")
    if hq_conf_existing == "verified" and brand.get("headquarters_city"):
        out["headquarters_city"] = brand["headquarters_city"]
        out["headquarters_confidence"] = "verified"
    else:
        out["headquarters_city"] = extracted.get("headquarters_city")
        out["headquarters_confidence"] = extracted.get("headquarters_confidence", "unknown")

    _apply_site_store_fields(out, extracted)
    if brand.get("_site_store_confidence") == "verified" and brand.get("_site_store_addresses"):
        out["_site_store_addresses"] = brand["_site_store_addresses"]
        out["_site_store_count"] = brand.get("_site_store_count")
        out["_site_store_confidence"] = "verified"

    return out


# ============================================================================
# Google Places + merge (unchanged behaviour)
# ============================================================================

async def _enrich_with_google_places(
    brands_data: List[Dict],
    city_ctx: CityContext,
    max_concurrent: int = 5,
) -> List[Dict]:
    sem = asyncio.Semaphore(max_concurrent)
    target_city = city_ctx.query

    async def enrich_one(brand: Dict) -> Dict:
        async with sem:
            brand_name = brand.get("name", "")
            country = brand.get("origin_country", "") or city_ctx.country or ""
            if not brand_name:
                return brand
            try:
                site_store_conf = (
                    brand.get("_site_store_confidence") or "unknown"
                ).lower()
                count_all_locations = site_store_conf != "verified"
                places_data = await enrich_with_places(
                    brand_name=brand_name,
                    city=target_city,
                    country=country,
                    website_url=brand.get("website_url", ""),
                    count_all_locations=count_all_locations,
                )
                if not count_all_locations:
                    logger.debug(
                        "  Places: skip global count for %s (site stores verified)",
                        brand_name,
                    )
                local_addr = places_data.get("local_store_address")
                if local_addr and not city_in_text(city_ctx, local_addr):
                    local_addr = None
                brand["local_store_address"] = local_addr
                brand["_places_store_count"] = places_data.get("places_store_count", 0)
                places_locs = places_data.get("places_locations", [])
                brand["_places_locations"] = [
                    addr for addr in places_locs if city_in_text(city_ctx, addr or "")
                ]
                phone = places_data.get("local_store_phone") or places_data.get("places_phone")
                if phone and not brand.get("contact_phone"):
                    brand["contact_phone"] = phone
            except Exception as e:
                logger.warning("Google Places error for %s: %s", brand_name, e)
                brand.setdefault("_places_store_count", 0)
                brand.setdefault("_places_locations", [])
            return brand

    return list(await asyncio.gather(*(enrich_one(b) for b in brands_data)))


def _merge_and_validate_locations(brands: List[Dict], city_ctx: CityContext) -> List[Dict]:
    for brand in brands:
        merged = merge_store_data(
            site_addresses=brand.pop("_site_store_addresses", []),
            site_count=brand.pop("_site_store_count", None),
            site_confidence=brand.pop("_site_store_confidence", "unknown"),
            places_addresses=brand.pop("_places_locations", []),
            places_count=brand.pop("_places_store_count", 0),
        )
        brand["store_count"] = merged["store_count"]
        brand["store_locations"] = merged["store_locations"]
        brand["store_count_confidence"] = merged["store_count_confidence"]
        validate_location_data(brand, city_ctx)
        brand.pop("_places_store_count", None)
        brand.pop("_places_locations", None)
    return brands


def _prepare_working_brands(filtered: List[Dict]) -> List[Dict]:
    """Normalize filter output into enrich working rows."""
    rows = []
    for b in filtered:
        rows.append({
            "url": b.get("url", b.get("website_url", "")),
            "website_url": b.get("url", b.get("website_url", "")),
            "brand_name": b.get("brand_name", b.get("name", b.get("title", ""))),
            "title": b.get("title", ""),
            "text": b.get("text", ""),
            "highlights": b.get("highlights", ""),
            "site_store_confidence": "unknown",
            "_site_store_addresses": [],
            "_site_store_count": None,
        })
    return rows


async def _enrich_cached_brands_local_only(
    brands: List[Dict],
    city_ctx: CityContext,
    target_city: str,
    progress: List[str],
) -> tuple:
    """Reuse brand_facts; only Google Places + city validation."""
    if not brands:
        return [], city_ctx

    hq_cities = [b["headquarters_city"] for b in brands if b.get("headquarters_city")]
    if hq_cities:
        city_ctx = await batch_check_hq_cities_against_target(city_ctx, hq_cities)

    progress.append(f"📦 Presença local (brand_facts): {len(brands)} marcas")
    brands = await _enrich_with_google_places(brands, city_ctx)
    brands = _merge_and_validate_locations(brands, city_ctx)
    return brands, city_ctx


async def _run_full_enrich_pipeline(
    working: List[Dict],
    target_city: str,
    target_country: str,
    city_ctx: CityContext,
    progress: List[str],
) -> tuple:
    """Full enrich path (prefill → Exa → LLM → HQ batch → Places → validate)."""
    prefilled = 0
    for brand in working:
        pre = prefill_from_discovery(brand)
        if pre:
            apply_prefill(brand, pre)
            if pre.get("contact_email"):
                brand["contact_email"] = pre["contact_email"]
            if pre.get("site_store_confidence") == "verified":
                brand["_site_store_addresses"] = pre.get("site_store_addresses", [])
                brand["_site_store_count"] = pre.get("site_store_count")
                brand["_site_store_confidence"] = "verified"
            prefilled += 1
    progress.append(f"✅ Prefill discovery: {prefilled}/{len(working)} marcas com dados iniciais")

    needs_price = sum(1 for b in working if _needs_exa_price(b))
    needs_about = sum(1 for b in working if _needs_exa_about(b))
    needs_stores = sum(1 for b in working if _needs_exa_stores(b))
    progress.append(
        f"🔎 Exa suplementar: preços={needs_price}, sede={needs_about}, lojas={needs_stores}"
    )
    exa_contents = await _batch_fetch_exa_supplements(working)
    fetched = sum(1 for e in exa_contents if any(e.values()))
    progress.append(f"✅ Exa suplementar: conteúdo extra em {fetched}/{len(working)} marcas")

    total_batches = (len(working) + ENRICH_BATCH_SIZE - 1) // ENRICH_BATCH_SIZE
    llm_sem = (
        asyncio.Semaphore(ENRICH_LLM_BATCH_CONCURRENT)
        if ENRICH_LLM_BATCH_CONCURRENT > 0
        else None
    )

    async def _run_unified_batch(batch_start: int) -> tuple:
        if llm_sem:
            async with llm_sem:
                return await _run_unified_batch_inner(batch_start)
        return await _run_unified_batch_inner(batch_start)

    async def _run_unified_batch_inner(batch_start: int) -> tuple:
        batch = working[batch_start: batch_start + ENRICH_BATCH_SIZE]
        batch_exa = exa_contents[batch_start: batch_start + ENRICH_BATCH_SIZE]
        batch_num = (batch_start // ENRICH_BATCH_SIZE) + 1
        extracted = await _extract_structured_batch(batch, batch_exa, target_city, target_country)
        merged_rows = []
        for i, row in enumerate(extracted):
            if i < len(batch):
                merged_rows.append(_merge_extracted_into_brand(batch[i], row, batch[i]))
        return batch_start, batch_num, merged_rows

    batch_starts = list(range(0, len(working), ENRICH_BATCH_SIZE))
    progress.append(f"  🔬 LLM unified: {total_batches} batches em paralelo")
    batch_results = await asyncio.gather(*[_run_unified_batch(bs) for bs in batch_starts])
    batch_results.sort(key=lambda x: x[0])
    all_structured: List[Dict] = []
    for _bs, batch_num, merged_rows in batch_results:
        all_structured.extend(merged_rows)
        progress.append(f"  ✓ LLM batch {batch_num}/{total_batches} ({len(merged_rows)} marcas)")
    progress.append(f"✅ Extracção única: {len(all_structured)} marcas")

    needing_hq = [
        b for b in all_structured
        if b.get("headquarters_confidence") != "verified" and not b.get("headquarters_city")
    ]
    if needing_hq:
        progress.append(f"🏢 HQ knowledge batch: {len(needing_hq)} marcas...")
        await resolve_headquarters_via_llm_batch(needing_hq)

    city_ctx = await batch_check_hq_cities_against_target(
        city_ctx,
        [b["headquarters_city"] for b in all_structured if b.get("headquarters_city")],
    )
    hq_resolved = sum(1 for b in all_structured if b.get("headquarters_city"))
    progress.append(f"✅ Sede: {hq_resolved}/{len(all_structured)} marcas")

    progress.append(f"📍 Google Places para {len(all_structured)} marcas...")
    all_structured = await _enrich_with_google_places(all_structured, city_ctx)
    places_with = sum(
        1 for b in all_structured
        if b.get("_places_store_count", 0) > 0 or b.get("local_store_address")
    )
    progress.append(f"✅ Google Places: {places_with}/{len(all_structured)}")

    enriched = _merge_and_validate_locations(all_structured, city_ctx)
    progress.append(f"✅ Localização validada: {len(enriched)} marcas")
    return enriched, city_ctx


# ============================================================================
# MAIN NODE
# ============================================================================

async def enrich_node(state: Union[ProspectorState, Dict[str, Any]]) -> Dict[str, Any]:
    target_city = state.get("target_city") if isinstance(state, dict) else getattr(state, "target_city", "")
    target_country = state.get("target_country") if isinstance(state, dict) else getattr(state, "target_country", "")
    filtered_brands = state.get("filtered_brands") if isinstance(state, dict) else getattr(state, "filtered_brands", [])

    t_node = step_begin(
        logger, "N3_ENRICH", target_city,
        f"Enriquecer {len(filtered_brands)} marcas (brand_facts → full ou local-only).",
    )
    progress = [f"📊 Enriquecendo {len(filtered_brands)} marcas..."]

    if not filtered_brands:
        step_end(logger, "N3_ENRICH", target_city, t_node, "sem marcas")
        return {"enriched_brands": [], "progress": progress + ["⚠️ Nenhuma marca para enriquecer"]}

    city_ctx = await resolve_target_city_context(target_city)
    if not target_country and city_ctx.country:
        target_country = city_ctx.country

    working = _prepare_working_brands(filtered_brands)

    t_cache = step_begin(logger, "N3_CACHE_BRAND_FACTS", target_city,
                         f"Verificar brand_facts para {len(working)} marcas.")
    domains = [extract_domain(b.get("website_url") or b.get("url", "")) for b in working]
    facts_by_domain = await get_brand_facts_batch(domains)
    ttl_days = get_brand_facts_ttl_days()

    cache_hit: List[Dict] = []
    cache_miss: List[Dict] = []
    for brand in working:
        domain = extract_domain(brand.get("website_url") or brand.get("url", ""))
        facts = facts_by_domain.get(domain) if domain else None
        if facts and is_brand_facts_fresh(facts.get("updated_at"), ttl_days):
            apply_brand_facts_to_brand(brand, facts)
            cache_hit.append(brand)
        else:
            cache_miss.append(brand)

    step_end(
        logger, "N3_CACHE_BRAND_FACTS", target_city, t_cache,
        hits=len(cache_hit), misses=len(cache_miss), ttl_days=ttl_days,
    )
    progress.append(
        f"📦 brand_facts: {len(cache_hit)} cache hit, {len(cache_miss)} enrich completo "
        f"(TTL {ttl_days}d)"
    )

    enriched_by_url: Dict[str, Dict] = {}

    if cache_miss:
        t_full = step_begin(logger, "N3_FULL_ENRICH", target_city,
                            f"Enrich completo para {len(cache_miss)} marcas.")
        full_enriched, city_ctx = await _run_full_enrich_pipeline(
            cache_miss, target_city, target_country, city_ctx, progress
        )
        step_end(logger, "N3_FULL_ENRICH", target_city, t_full, brands=len(full_enriched))
        for b in full_enriched:
            url = b.get("website_url") or ""
            if url:
                enriched_by_url[url] = b

    if cache_hit:
        t_local = step_begin(logger, "N3_LOCAL_ONLY", target_city,
                             f"Só presença local para {len(cache_hit)} marcas (cache).")
        local_enriched, city_ctx = await _enrich_cached_brands_local_only(
            cache_hit, city_ctx, target_city, progress
        )
        step_end(logger, "N3_LOCAL_ONLY", target_city, t_local, brands=len(local_enriched))
        for b in local_enriched:
            url = b.get("website_url") or ""
            if url:
                enriched_by_url[url] = b

    enriched = []
    for brand in working:
        url = brand.get("website_url") or brand.get("url", "")
        if url in enriched_by_url:
            enriched.append(enriched_by_url[url])

    t_save_facts = step_begin(logger, "N3_SAVE_BRAND_FACTS", target_city, "Persistir brand_facts.")
    saved_facts = await upsert_brand_facts_from_brands(enriched)
    step_end(logger, "N3_SAVE_BRAND_FACTS", target_city, t_save_facts, upserted=saved_facts)
    if saved_facts:
        progress.append(f"💾 brand_facts actualizados: {saved_facts} domínios")

    for b in enriched:
        logger.info(
            "  Enriched: %s | €%s | %d stores (%s) | HQ=%s (%s) | presence=%s",
            b.get("name", "?"),
            b.get("avg_suit_price_eur", "?"),
            b.get("store_count", 0),
            b.get("store_count_confidence", "?"),
            b.get("headquarters_city", "?"),
            b.get("headquarters_confidence", "?"),
            b.get("city_presence_type", "?"),
        )

    step_end(logger, "N3_ENRICH", target_city, t_node, total=len(enriched))
    return {
        "enriched_brands": enriched,
        "target_city_context": city_ctx.to_dict(),
        "progress": progress,
    }
