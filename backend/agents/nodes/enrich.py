"""
Node 3: Enrich
Takes filtered brands and:
  1. Calls Exa per brand to find pricing pages (suits price)
  2. Extracts structured data from combined Exa content via LLM
  3. Calls Google Places API for store count and addresses
"""

import asyncio
import json
import logging
import os
from typing import List, Dict, Any, Union

from exa_py import Exa
from models import ProspectorState, BrandLead
from services.google_places import enrich_with_places
from .utils import get_llm
from .pipeline_timing import step_begin, step_end

logger = logging.getLogger("node.enrich")

ENRICH_BATCH_SIZE = 6
EXA_PRICE_MAX_CONCURRENT = 5
EXA_PRICE_MAX_CHARS = 5000


# ============================================================================
# EXA: PRICE LOOKUP PER BRAND
# ============================================================================

async def _exa_price_lookup(
    exa: Exa,
    brand_name: str,
    brand_url: str,
    max_concurrent_sem: asyncio.Semaphore,
) -> str:
    """
    Call Exa to find pricing information for a specific brand.
    Searches for "{brand_name} suits price" and returns the text content.
    """
    async with max_concurrent_sem:
        query = f"{brand_name} suits price"
        try:
            response = await asyncio.to_thread(
                exa.search,
                query,
                num_results=3,
                type="auto",
                include_domains=[brand_url.split("//")[-1].split("/")[0].replace("www.", "")],
                contents={"text": {"maxCharacters": EXA_PRICE_MAX_CHARS}},
            )
            texts = []
            for result in response.results:
                if hasattr(result, "text") and result.text:
                    texts.append(result.text)
            if texts:
                combined = "\n---\n".join(texts)
                logger.info("  Exa price for %s: %d chars from %d results",
                            brand_name, len(combined), len(texts))
                return combined
        except Exception as e:
            logger.warning("  Exa price lookup failed for %s: %s — trying broader search", brand_name, e)

        # Fallback: broader search without domain restriction
        try:
            response = await asyncio.to_thread(
                exa.search,
                f"{brand_name} men's suits price collection",
                num_results=2,
                type="auto",
                contents={"text": {"maxCharacters": EXA_PRICE_MAX_CHARS}},
            )
            texts = []
            for result in response.results:
                if hasattr(result, "text") and result.text:
                    texts.append(result.text)
            if texts:
                combined = "\n---\n".join(texts)
                logger.info("  Exa price (broad) for %s: %d chars", brand_name, len(combined))
                return combined
        except Exception as e2:
            logger.warning("  Exa price broad search also failed for %s: %s", brand_name, e2)

        return ""


async def _batch_exa_price_lookup(
    brands: List[Dict],
) -> List[str]:
    """
    Run Exa price lookups for all brands in parallel (with concurrency limit).
    Returns list of price content strings, one per brand.
    """
    exa_key = os.environ.get("EXA_API_KEY")
    if not exa_key:
        logger.warning("No EXA_API_KEY — skipping price lookup")
        return [""] * len(brands)

    exa = Exa(api_key=exa_key)
    sem = asyncio.Semaphore(EXA_PRICE_MAX_CONCURRENT)

    tasks = [
        _exa_price_lookup(
            exa,
            brand_name=b.get("brand_name", b.get("name", b.get("title", ""))),
            brand_url=b.get("url", b.get("website_url", "")),
            max_concurrent_sem=sem,
        )
        for b in brands
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    price_texts = []
    for r in results:
        if isinstance(r, Exception):
            logger.warning("Exa price task exception: %s", r)
            price_texts.append("")
        else:
            price_texts.append(r or "")

    return price_texts


# ============================================================================
# EXA: EMAIL/CONTACT LOOKUP PER BRAND
# ============================================================================

async def _exa_email_lookup(
    exa: Exa,
    brand_name: str,
    brand_url: str,
    max_concurrent_sem: asyncio.Semaphore,
) -> str:
    """
    Call Exa to find contact email for a specific brand.
    Searches the brand's domain for contact pages.
    """
    import re
    async with max_concurrent_sem:
        domain = brand_url.split("//")[-1].split("/")[0].replace("www.", "")
        query = f"{brand_name} contact email"
        try:
            response = await asyncio.to_thread(
                exa.search,
                query,
                num_results=3,
                type="auto",
                include_domains=[domain],
                contents={"text": {"maxCharacters": 3000}},
            )
            for result in response.results:
                if hasattr(result, "text") and result.text:
                    emails = re.findall(
                        r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}',
                        result.text
                    )
                    valid = [
                        e for e in emails
                        if not any(x in e.lower() for x in ["noreply", "no-reply", "unsubscribe", "mailer-daemon"])
                        and not e.endswith(".png")
                        and not e.endswith(".jpg")
                    ]
                    preferred = [e for e in valid if any(
                        p in e.lower() for p in ["info@", "contact@", "hello@", "sales@", "enquir"]
                    )]
                    if preferred:
                        return preferred[0]
                    if valid:
                        return valid[0]
        except Exception as e:
            logger.debug("  Exa email lookup failed for %s: %s", brand_name, e)

        # Fallback: broader search
        try:
            response = await asyncio.to_thread(
                exa.search,
                f"{brand_name} email contact us",
                num_results=2,
                type="auto",
                contents={"text": {"maxCharacters": 2000}},
            )
            for result in response.results:
                if hasattr(result, "text") and result.text:
                    emails = re.findall(
                        r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}',
                        result.text
                    )
                    valid = [
                        e for e in emails
                        if not any(x in e.lower() for x in ["noreply", "no-reply", "unsubscribe", "mailer-daemon"])
                        and not e.endswith(".png")
                        and not e.endswith(".jpg")
                    ]
                    if valid:
                        return valid[0]
        except Exception as e2:
            logger.debug("  Exa email broad search also failed for %s: %s", brand_name, e2)

        return ""


async def _batch_exa_email_lookup(brands: List[Dict]) -> List[str]:
    """Run Exa email lookups for brands in parallel."""
    exa_key = os.environ.get("EXA_API_KEY")
    if not exa_key:
        logger.warning("No EXA_API_KEY — skipping email lookup")
        return [""] * len(brands)

    exa = Exa(api_key=exa_key)
    sem = asyncio.Semaphore(EXA_PRICE_MAX_CONCURRENT)

    tasks = [
        _exa_email_lookup(
            exa,
            brand_name=b.get("name", b.get("brand_name", "")),
            brand_url=b.get("website_url", b.get("url", "")),
            max_concurrent_sem=sem,
        )
        for b in brands
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    emails = []
    for r in results:
        if isinstance(r, Exception):
            logger.warning("Exa email task exception: %s", r)
            emails.append("")
        else:
            emails.append(r or "")

    return emails


# ============================================================================
# LLM: STRUCTURED DATA EXTRACTION
# ============================================================================

async def _extract_structured_batch(
    brands: List[Dict],
    price_contents: List[str],
    target_city: str,
    target_country: str,
) -> List[Dict]:
    """
    Use GPT-5.1 (deep model) to extract structured data.
    Combines original Exa content + dedicated price lookup content.
    """
    llm = get_llm(fast=False)

    candidates_block = "\n\n".join(
        f"=== BRAND {i+1} ===\n"
        f"URL: {b['url']}\n"
        f"BRAND NAME (from filter): {b.get('brand_name', '')}\n"
        f"GENERAL CONTENT:\n{(b.get('text', '') or b.get('highlights', ''))[:4000]}\n"
        f"PRICING PAGE CONTENT:\n{(price_contents[i] if i < len(price_contents) else '')[:3000]}"
        for i, b in enumerate(brands)
    )

    prompt = f"""You are a data analyst extracting structured information about menswear brands for a Portuguese suit manufacturer (Confeções Lança).

CITY: {target_city}
COUNTRY: {target_country}

For each brand below, extract structured data from BOTH the general content and pricing page content.
The PRICING PAGE CONTENT comes directly from the brand's website — it contains real product prices.
If information is not available, use null.

BRANDS ({len(brands)} total):
{candidates_block}

TASK: Extract structured data for each brand.
Return ONLY a JSON array with one object per brand, in SAME order:
[{{
  "name": "Brand Name",
  "website_url": "https://...",
  "origin_country": "Country where brand is headquartered",
  "headquarters_city": "City where brand HQ is located (from content or inferred)",
  "avg_suit_price_eur": 800,
  "price_range_min_eur": 500,
  "price_range_max_eur": 1200,
  "made_to_measure": true/false/null,
  "wool_percentage": "100%" or "mixed" or null,
  "brand_style": "Heritage/Premium/Contemporary/Luxury/Traditional",
  "business_model": "Retail/Bespoke/Multi-brand/Online+Retail",
  "company_overview": "2-3 sentences describing the brand, what they sell, and their positioning",
  "contact_email": "email found in content or null",
  "clothing_types": ["suits", "blazers", "trousers"],
  "target_gender": "men" or "unisex" or "women",
  "is_chain": true/false/null,
  "bespoke_only": true/false/null
}}]

PRICING RULES:
- PRIORITIZE prices from the PRICING PAGE CONTENT — these are real prices from the brand's site
- Convert all prices to EUR. Use approximate rates: £1 = €1.17, $1 = €0.93, CHF 1 = €1.05
- If only one price is found, use it as both min and max
- If no price found, set all price fields to null
- avg_suit_price_eur = midpoint of min and max

HEADQUARTERS RULES:
- headquarters_city = the city where the brand's HEAD OFFICE / HQ is located
- Look for mentions like "based in", "headquartered in", "founded in", address in footer/about
- If the brand only has ONE store, that city is likely the HQ city
- If unclear, use null

EMAIL RULES:
- Look for contact/info/sales email addresses in the content
- Prefer: sales@, info@, contact@, hello@ (general business emails)
- Do NOT use personal emails or noreply emails
- If not found, use null

Return ONLY the JSON array."""

    try:
        response = await llm.ainvoke(prompt)
        raw = response.content.replace("```json", "").replace("```", "").strip()
        results = json.loads(raw)
        if not isinstance(results, list):
            results = [results]
        return results
    except Exception as e:
        logger.warning("Enrich batch LLM error: %s — returning minimal data", e)
        return [
            {
                "name": b.get("brand_name", b.get("title", "")),
                "website_url": b["url"],
                "origin_country": None,
                "headquarters_city": None,
                "avg_suit_price_eur": None,
                "price_range_min_eur": None,
                "price_range_max_eur": None,
                "made_to_measure": None,
                "wool_percentage": None,
                "brand_style": None,
                "business_model": None,
                "company_overview": None,
                "contact_email": None,
                "clothing_types": [],
                "target_gender": None,
                "is_chain": None,
                "bespoke_only": None,
            }
            for b in brands
        ]


# ============================================================================
# GOOGLE PLACES ENRICHMENT
# ============================================================================

async def _enrich_with_google_places(
    brands_data: List[Dict],
    target_city: str,
    max_concurrent: int = 5,
) -> List[Dict]:
    """Call Google Places API for each brand to get store count and addresses."""
    sem = asyncio.Semaphore(max_concurrent)

    async def enrich_one(brand: Dict) -> Dict:
        async with sem:
            brand_name = brand.get("name", "")
            country = brand.get("origin_country", "")
            if not brand_name:
                return brand

            try:
                places_data = await enrich_with_places(
                    brand_name=brand_name,
                    city=target_city,
                    country=country or "",
                    website_url=brand.get("website_url", ""),
                )
                brand["store_count"] = places_data.get("places_store_count", 0)
                brand["store_locations"] = places_data.get("places_locations", [])
                brand["headquarters_address"] = places_data.get("places_address")
                if places_data.get("places_phone"):
                    brand["contact_phone"] = places_data["places_phone"]
            except Exception as e:
                logger.warning("Google Places error for %s: %s", brand_name, e)

            return brand

    results = await asyncio.gather(*(enrich_one(b) for b in brands_data))
    return list(results)


# ============================================================================
# MAIN NODE
# ============================================================================

async def enrich_node(state: Union[ProspectorState, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Node 3: Enrich.
    1. Exa price lookup per brand (parallel)
    2. LLM extracts structured data from combined content
    3. Google Places for store count and addresses
    """
    target_city = state.get("target_city") if isinstance(state, dict) else getattr(state, "target_city", "")
    target_country = state.get("target_country") if isinstance(state, dict) else getattr(state, "target_country", "")
    filtered_brands = state.get("filtered_brands") if isinstance(state, dict) else getattr(state, "filtered_brands", [])

    t_node = step_begin(logger, "N3_ENRICH", target_city,
                        f"Enriquecer {len(filtered_brands)} marcas: Exa preços + LLM + Google Places.")

    progress = [f"📊 Enriquecendo {len(filtered_brands)} marcas..."]

    if not filtered_brands:
        step_end(logger, "N3_ENRICH", target_city, t_node, "sem marcas para enriquecer")
        return {
            "enriched_brands": [],
            "progress": progress + ["⚠️ Nenhuma marca para enriquecer"],
        }

    # Phase 1: Exa price lookup (parallel, all brands at once)
    t_prices = step_begin(logger, "N3a_EXA_PRICES", target_city,
                          f"Exa price lookup para {len(filtered_brands)} marcas.")
    progress.append(f"💰 Pesquisando preços no Exa para {len(filtered_brands)} marcas...")

    price_contents = await _batch_exa_price_lookup(filtered_brands)

    brands_with_prices = sum(1 for p in price_contents if p)
    step_end(logger, "N3a_EXA_PRICES", target_city, t_prices,
             brands_with_prices=brands_with_prices,
             brands_without=len(filtered_brands) - brands_with_prices)
    progress.append(f"✅ Preços encontrados: {brands_with_prices}/{len(filtered_brands)} marcas")

    # Phase 2: LLM structured extraction in batches
    t_llm = step_begin(logger, "N3b_LLM_EXTRACT", target_city,
                        "Extrair dados estruturados via LLM (com conteúdo de preços).")
    all_structured = []

    for batch_start in range(0, len(filtered_brands), ENRICH_BATCH_SIZE):
        batch = filtered_brands[batch_start:batch_start + ENRICH_BATCH_SIZE]
        batch_prices = price_contents[batch_start:batch_start + ENRICH_BATCH_SIZE]
        batch_num = (batch_start // ENRICH_BATCH_SIZE) + 1
        total_batches = (len(filtered_brands) + ENRICH_BATCH_SIZE - 1) // ENRICH_BATCH_SIZE

        logger.info("Enrich LLM batch %d/%d (%d brands)", batch_num, total_batches, len(batch))
        progress.append(f"  🔬 LLM batch {batch_num}/{total_batches}")

        batch_results = await _extract_structured_batch(batch, batch_prices, target_city, target_country)

        for i, result in enumerate(batch_results):
            if i < len(batch):
                if not result.get("website_url"):
                    result["website_url"] = batch[i]["url"]
                if not result.get("name"):
                    result["name"] = batch[i].get("brand_name", batch[i].get("title", ""))

        all_structured.extend(batch_results)

    step_end(logger, "N3b_LLM_EXTRACT", target_city, t_llm,
             brands_extracted=len(all_structured))
    progress.append(f"✅ Dados extraídos para {len(all_structured)} marcas")

    # Phase 3: Exa email lookup for brands without email
    brands_without_email = [b for b in all_structured if not b.get("contact_email")]
    if brands_without_email:
        t_email = step_begin(logger, "N3c_EXA_EMAIL", target_city,
                             f"Exa email lookup para {len(brands_without_email)} marcas sem email.")
        progress.append(f"📧 Pesquisando emails para {len(brands_without_email)} marcas...")

        email_results = await _batch_exa_email_lookup(brands_without_email)
        for brand_data, email in zip(brands_without_email, email_results):
            if email:
                brand_data["contact_email"] = email

        found_emails = sum(1 for e in email_results if e)
        step_end(logger, "N3c_EXA_EMAIL", target_city, t_email,
                 found=found_emails, total=len(brands_without_email))
        progress.append(f"✅ Emails encontrados: {found_emails}/{len(brands_without_email)}")

    # Phase 4: Google Places enrichment
    t_places = step_begin(logger, "N3d_GOOGLE_PLACES", target_city,
                          f"Google Places API para {len(all_structured)} marcas.")
    progress.append(f"📍 Chamando Google Places para {len(all_structured)} marcas...")

    enriched = await _enrich_with_google_places(all_structured, target_city)

    places_with_data = sum(1 for b in enriched if b.get("store_count", 0) > 0)
    step_end(logger, "N3d_GOOGLE_PLACES", target_city, t_places,
             brands_with_places=places_with_data)
    progress.append(f"✅ Google Places: {places_with_data}/{len(enriched)} com dados de lojas")

    for b in enriched:
        logger.info("  Enriched: %s | €%s | %d stores | MTM=%s | Wool=%s",
                     b.get("name", "?"),
                     b.get("avg_suit_price_eur", "?"),
                     b.get("store_count", 0),
                     b.get("made_to_measure", "?"),
                     b.get("wool_percentage", "?"))

    step_end(logger, "N3_ENRICH", target_city, t_node,
             total_enriched=len(enriched))

    return {
        "enriched_brands": enriched,
        "progress": progress,
    }
