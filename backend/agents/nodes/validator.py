"""
Node 3: Validation Node V3
2-Phase LLM Analysis: Fast Triage (GPT-5.1-mini) + Deep Analysis (GPT-5.1)
Multi-language keyword scoring, context-aware price extraction, confidence scoring.
"""

import logging
from typing import List, Dict, Any, Union, Optional
import asyncio
import json
import re
from models import ProspectorState, BrandLead, ExtractedContent

logger = logging.getLogger("node.validator")
from config import CONFECOS_LANCA_PROFILE
from data.premium_locations import detect_premium_location, calculate_location_score
from data.multilingual_keywords import (
    calculate_keyword_score,
    is_known_chain,
)
from urllib.parse import urlparse
from .utils import get_llm, get_domain_from_url, normalize_url
from services.content_scraper import batch_extract_content, enrich_content_with_prices
from services.price_extractor import extract_price_from_content
from services.vector_db import find_similar_clients
from services.client_analysis import generate_rich_client_examples
from services.database import is_domain_suppressed, extract_domain
from services.google_places import enrich_with_places
from services.field_merger import merge_brand_data
from data.lanca_clients import LANCA_CLIENTS
from data.marketplace_allowlist import is_allowlisted_marketplace


# ============================================================================
# HELPERS
# ============================================================================

_PRICING_KW_RE = re.compile(
    r"(?:from|starting\s+at|a\s+partir\s+de|à\s+partir\s+de|ab|desde|da|shop\s+now|buy\s+now|add\s+to\s+cart|€|£|\$|¥|kr)",
    re.IGNORECASE,
)


def _has_pricing_keywords(text: str) -> bool:
    """Check if text contains pricing-related keywords or currency symbols."""
    if not text:
        return False
    return bool(_PRICING_KW_RE.search(text[:5000]))


# ============================================================================
# STRUCTURED STAGE LOGGING
# ============================================================================

def stage_log(stage: str, city: str, candidates_in: int, candidates_out: int, **extra):
    """Emit a structured log line at each phase boundary for the coverage audit."""
    parts = [f"[stage={stage}]", f"[city={city}]",
             f"[candidates_in={candidates_in}]", f"[candidates_out={candidates_out}]"]
    for k, v in extra.items():
        parts.append(f"[{k}={v}]")
    logger.info(" ".join(parts))


# ============================================================================
# BLOG / MEDIA / MARKETPLACE FILTER (free, no API cost)
# ============================================================================

BLOG_INDICATORS = [
    "/blog", "/article", "/post", "/news",
    "wordpress.com", "blogspot.com", "medium.com",
    "/tag/", "/category/", "/archive/",
]

MEDIA_DOMAINS = {
    "permanentstyle.com", "styleforum.net", "mrporter.com",
    "farfetch.com", "matchesfashion.com", "ssense.com",
    "gq.com", "esquire.com", "vogue.com",
    "businessoffashion.com", "highsnobiety.com",
    "therake.com", "parfrenchtouch.com",
}


def is_blog_or_media(url: str) -> bool:
    """Filter out blogs, media sites, and marketplaces. Free check.
    Respects the marketplace allowlist (own-brand labels get through)."""
    if is_allowlisted_marketplace(url):
        return False
    url_lower = url.lower()
    domain = urlparse(url).netloc.lower().replace("www.", "")
    if domain in MEDIA_DOMAINS:
        return True
    return any(ind in url_lower for ind in BLOG_INDICATORS)

# Limit global validation concurrency (e.g., 3 city searches at a time)
validation_semaphore = asyncio.Semaphore(3)


# ============================================================================
# APPOINTMENT-ONLY / NO-CATALOG DETECTION (free, no API cost)
# ============================================================================

# Keywords that strongly indicate appointment-only / no-browse experience
APPOINTMENT_KEYWORDS = [
    # English
    "book an appointment", "book appointment", "schedule an appointment",
    "schedule appointment", "by appointment only", "appointment only",
    "book a consultation", "book consultation", "private appointment",
    "request an appointment", "reserve an appointment",
    "book a fitting", "schedule a fitting", "book your visit",
    "consultation required", "appointment required",
    # French
    "prendre rendez-vous", "sur rendez-vous", "rendez-vous uniquement",
    # Italian
    "su appuntamento", "solo su appuntamento", "prenota un appuntamento",
    # German
    "termin vereinbaren", "nur nach vereinbarung", "nach terminvereinbarung",
    # Spanish
    "reservar cita", "solo con cita", "cita previa",
    # Portuguese
    "marcar consulta", "apenas com marcação", "só com marcação",
]

# Keywords that indicate a browseable product catalog exists
CATALOG_KEYWORDS = [
    "add to cart", "add to bag", "add to basket", "shop now", "buy now",
    "view collection", "browse collection", "our collection",
    "shop suits", "shop jackets", "shop trousers",
    "product details", "size guide", "select size",
    "in stock", "out of stock", "delivery", "shipping",
    "€", "£", "$",  # Price symbols indicate visible pricing
    "añadir al carrito", "ajouter au panier", "in den warenkorb",
    "aggiungi al carrello", "adicionar ao carrinho",
]


def is_appointment_only(content: str) -> bool:
    """
    Detect if a site is appointment-only with no browsable catalog.
    Returns True if the site has appointment keywords but NO catalog/shop indicators.
    This is a FREE check (no API cost).
    """
    if not content:
        return False
    
    content_lower = content.lower()
    
    # Count appointment signals
    appointment_signals = sum(1 for kw in APPOINTMENT_KEYWORDS if kw in content_lower)
    
    # Count catalog/shop signals
    catalog_signals = sum(1 for kw in CATALOG_KEYWORDS if kw in content_lower)
    
    # Appointment-only if: multiple appointment signals AND very few catalog signals
    if appointment_signals >= 2 and catalog_signals <= 1:
        return True
    
    # Strong appointment-only signal even with 1 match if zero catalog
    if appointment_signals >= 1 and catalog_signals == 0:
        return True
    
    return False


# ============================================================================
# LANGUAGE DETECTION (lightweight, no API cost)
# ============================================================================

def detect_language(text: str) -> Optional[str]:
    """
    Detect the language of text content. Uses simple heuristics first, 
    falls back to None if uncertain. No API cost.
    """
    if not text:
        return None
    
    sample = text[:3000].lower()
    
    # Simple heuristic based on common words
    lang_indicators = {
        "it": ["il ", " di ", " del ", " della ", " che ", " sono ", " con ", " per ", " abiti ", " uomo "],
        "fr": [" le ", " la ", " les ", " des ", " du ", " est ", " nous ", " avec ", " pour ", " homme "],
        "de": [" der ", " die ", " das ", " und ", " ist ", " mit ", " für ", " herren ", " anzug "],
        "es": [" el ", " la ", " los ", " las ", " del ", " con ", " para ", " hombre ", " traje "],
        "pt": [" o ", " os ", " do ", " da ", " dos ", " das ", " com ", " para ", " homem ", " fato "],
    }
    
    best_lang = "en"
    best_score = 0
    
    for lang, indicators in lang_indicators.items():
        score = sum(1 for ind in indicators if ind in sample)
        if score > best_score and score >= 3:  # Need at least 3 matches
            best_score = score
            best_lang = lang
    
    return best_lang


# ============================================================================
# PHASE 1: FAST TRIAGE (GPT-5.1-mini — ~$0.02 per candidate)
# ============================================================================

TRIAGE_BATCH_SIZE = 12


async def triage_batch(contents: List[ExtractedContent], target_city: str) -> List[Dict[str, Any]]:
    """
    Phase 1: Quick triage with fast model. Evaluates a BATCH of candidates at once.
    Returns a list of {url, score, ...} dicts.
    Processes up to TRIAGE_BATCH_SIZE (12) candidates per LLM call, reducing
    token overhead from per-candidate system prompts and saving 5-7x tokens.
    """
    llm = get_llm(fast=True, temperature=0)

    candidates_block = "\n\n".join(
        f"--- CANDIDATE {i+1} ---\nURL: {c.url}\n{(c.content or '')[:2500]}"
        for i, c in enumerate(contents)
    )
    url_list = [c.url for c in contents]

    prompt = f"""You are a quick-filter for a Portuguese suit manufacturer (Confeções Lança) looking for retail partners.

TARGET: Independent boutiques selling mid-to-high range tailored menswear, up to 20 stores.
Price ranges: suits $500–$2,300, jackets $300–$1,380, trousers $200–$920.
NOT ultra-luxury/bespoke ateliers. Brands with own label collections or RTW are a plus.

⚠️ PHYSICAL PRESENCE RULE:
Brand MUST have a physical store, showroom, or strong retail presence in {target_city}.
If online-only, set city_match=false.

CANDIDATES ({len(contents)} total):
{candidates_block}

TASK: Rate EACH candidate (1-10) and classify it.

Return ONLY a JSON array with one object per candidate, in SAME order:
[{{"url":"...", "score":1-10, "reason":"short sentence", "is_menswear":true/false, "estimated_price_tier":"budget|mid|premium|luxury|unknown", "estimated_stores":"independent_1_20|chain_20_plus|unknown", "is_chain":true/false, "city_match":true/false, "is_bespoke_only":true/false, "appointment_only":true/false, "prices_visible":true/false}}]

SCORING: 9-10 perfect match, 7-8 good, 5-6 worth investigating, 3-4 probably not, 1-2 definitely not.
RULES: No city evidence → city_match=false, cap 4. Ultra-luxury → cap 5. Appointment-only → -2 pts. Hidden prices → -2 pts.
BE INCLUSIVE: menswear + HQ in {target_city} + visible prices → at least 5.

Return ONLY the JSON array."""

    try:
        response = await llm.ainvoke(prompt)
        raw = response.content.replace("```json", "").replace("```", "").strip()
        results = json.loads(raw)
        if not isinstance(results, list):
            results = [results]
        for i, r in enumerate(results):
            if "url" not in r or not r["url"]:
                r["url"] = url_list[i] if i < len(url_list) else ""
        return results
    except Exception as e:
        logger.warning("Batch triage error: %s", e)
        return [
            {
                "url": c.url, "score": 5, "reason": "Batch triage error — defaulting to neutral",
                "is_menswear": True, "estimated_price_tier": "unknown",
                "estimated_stores": "unknown", "is_chain": False,
                "city_match": True, "is_bespoke_only": False,
                "appointment_only": False, "prices_visible": False,
            }
            for c in contents
        ]


async def triage_candidate(content: ExtractedContent, target_city: str) -> Dict[str, Any]:
    """Legacy single-candidate triage. Wraps triage_batch for backward compat."""
    results = await triage_batch([content], target_city)
    return results[0] if results else {
        "url": content.url, "score": 5, "reason": "Fallback",
        "is_menswear": True, "city_match": True, "is_chain": False,
    }


# ============================================================================
# PHASE 2: DEEP ANALYSIS (GPT-5.1 — batches of 5-8)
# ============================================================================

async def deep_analyze_batch(
    extracted_contents: List[ExtractedContent],
    price_threshold_usd: float,
    target_city: str,
) -> List[BrandLead]:
    """
    Phase 2: Deep analysis in batches of 5-8.
    Uses GPT-5.1 for maximum quality.
    """
    llm = get_llm(fast=False, temperature=0.2)

    sites_content = "\n\n".join(
        [
            f"=== CANDIDATE {i+1} ===\nURL: {e.url}\nCONTENT: {e.content[:8000]}"
            for i, e in enumerate(extracted_contents)
            if e.content
        ]
    )

    if not sites_content.strip():
        logger.warning(
            "│     Deep analysis skipped: no text content in batch (urls=%s)",
            [e.url for e in extracted_contents],
        )
        return []

    prompt = f"""You are the FINAL selection agent for "Confeções Lança". 
    {CONFECOS_LANCA_PROFILE}
    
    CLIENTES REAIS DA LANÇA (Use as "Golden Profile"):
    {generate_rich_client_examples(n_examples=3)}
    
    CANDIDATES TO EVALUATE (only {len(extracted_contents)}):
    {sites_content}
    
    TASK: Return a JSON array of brands that are good partnership opportunities.
    LANGUAGE: Use PORTUGUESE (PORTUGAL) for all descriptive text.
    
    ⚠️ MANDATORY PHYSICAL PRESENCE RULE — READ CAREFULLY:
    The brand MUST have a physical store, showroom, or retail presence in {target_city}.
    Brands that are 100% online with no locations in {target_city} MUST be EXCLUDED.
    Very Important: Even if the brand has a store in {target_city}, try to find out where their ACTUAL Headquarters is located.
    Format the "headquartersAddress" field explicitly mentioning the HQ, e.g., "Sede em Londres (Loja em {target_city})" or "Sede em Nova Iorque".
    
    PRICE RANGES (3 product categories):
    - Complete suits (jacket + trousers): $500–$2,300
    - Jackets only: $300–$1,380
    - Trousers only: $200–$920
    Extract prices for each category when available.
    
    CRITICAL RULES:
    1. ENTITY DEDUPLICATION: If two candidates are actually the same brand, return only the best one.
    2. CONTACT EXTRACTION: Search content for CEO, Founder, Owner names, emails, LinkedIn profiles.
    3. SEMANTIC FIT: Evaluate how closely the brand matches the "Golden Profile".
    4. PRICE EXTRACTION: Find actual prices for suits, jackets AND trousers separately. Convert to EUR if in another currency.
    5. PRESENCE VALIDATION: If you cannot confirm the brand has a physical presence in {target_city}, EXCLUDE it. DO NOT exclude it if headquartered elsewhere, as long as they have a store.
    6. APPOINTMENT-ONLY PENALTY: If the brand's website requires booking an appointment to see products, DO NOT exclude it, but reduce fitScore by 20 points.
    7. PRICE VISIBILITY & NOTES: Se não houver preços no site, MAS houver indicação como "prices starting at $1500", preenche o "avgPrice" com esse valor, MAS OBRIGATORIAMENTE coloca no campo "priceNote" o texto "A partir de [VALOR]". Se nem isso estiver presente (ou seja, preços 100% indisponíveis), no campo "priceNote" escreve estritamente a frase: "O site não contém os preços dos fatos", e coloca o "avgPrice" como 0. NUNCA inventes ou deduzas o "avgPrice" por ti próprio — se não há provas do preço no texto, devolve sempre 0.
    8. BE INCLUSIVE: Include ALL brands that sell menswear (suits, trousers, waistcoats), HAVE A STORE in {target_city}, have up to 20 stores, and are within the target price ranges.
    9. NULL FOR UNGROUNDED FIELDS: Return null for ANY field you cannot ground in the provided source text. Especially: contactPhone, contactEmail, contactName, headquartersAddress, woolPercentage. NEVER fabricate or guess these values.
    
    FORMAT: Return ONLY a JSON array:
    [
      {{
        "name": "Brand Name", "url": "URL", "storeCount": int, "isChain": bool,
        "avgPrice": float, "avgJacketPrice": float|null, "avgTrousersPrice": float|null,
        "priceSource": "found"|"not_public", "priceNote": "...",
        "woolPercentage": "...", "madeToMeasure": bool, "bespokeOnly": bool,
        "appointmentOnly": bool, "pricesVisible": bool,
        "brandStyle": "...", "businessModel": "...",
        "detailedDescription": "...", 
        "headquartersAddress": "HQ address in {target_city}",
        "storeLocations": ["All store addresses"], 
        "whySelected": "...",
        "city": "{target_city}", "country": "...", "locationQuality": "premium"|"standard",
        "fitScore": int,
        "hasHeadquarters": true/false,
        "contactName": "...", "contactRole": "...", "contactEmail": "...", "contactPhone": "..."
      }}
    ]
    
    Return ONLY JSON."""

    raw = ""
    try:
        response = await llm.ainvoke(prompt)
        raw = response.content.replace("```json", "").replace("```", "").strip()
        candidates = json.loads(raw)
        if not isinstance(candidates, list):
            candidates = [candidates]
        if not candidates:
            logger.warning(
                "│     Deep analysis: model returned empty array (candidates_in_batch=%d, raw_chars=%d)",
                len(extracted_contents),
                len(raw),
            )
        for c in candidates:
            logger.info("│     Deep → %s (fitScore=%s, price=%s)", c.get("name"), c.get("fitScore"), c.get("avgPrice"))
        return candidates
    except Exception as e:
        logger.error("│     Deep analysis batch error: %s", e)
        if raw:
            logger.error("│     Deep analysis raw prefix: %s", raw[:800])
        return []


# ============================================================================
# MAIN VALIDATION NODE
# ============================================================================

async def validation_node(
    state: Union[ProspectorState, Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Validation Node V3 — 2-Phase Architecture:
    
    Phase 0: Scrape + Known Chain Exclusion + Multi-Language Keyword Scoring
    Phase 1: Fast Triage (GPT-5.1-mini, per-candidate, ~$0.02 each)
    Phase 2: Deep Analysis (GPT-5.1, batches of 3, ~$0.50 each)
    """
    async with validation_semaphore:
        target_city = (
            state.target_city
            if hasattr(state, "target_city")
            else state.get("target_city")
        )
        price_threshold_usd = (
            state.price_threshold_usd
            if hasattr(state, "price_threshold_usd")
            else state.get("price_threshold_usd", 0)
        )
        search_results = (
            state.search_results
            if hasattr(state, "search_results")
            else state.get("search_results", [])
        )

    logger.info("┌─── NODE 3: VALIDATION ────────────────────────────")
    logger.info("│ City: %s | Price threshold: $%.0f", target_city, price_threshold_usd)
    new_progress = []

    if not search_results:
        return {
            "potential_brands": [],
            "progress": ["⚠️ Nenhum resultado de busca para processar"],
        }

    try:
        # ================================================================
        # PHASE 0: URL AGGREGATION + KNOWN CHAIN EXCLUSION
        # ================================================================
        # Existing Clients Suppression
        client_domains = {extract_domain(c.get("url", "")) for c in LANCA_CLIENTS if c.get("url")}
        client_names = {c["name"].lower().strip() for c in LANCA_CLIENTS}
        
        candidate_urls = []
        url_to_origin = {}
        seen_domains = set()
        excluded_chains = 0
        excluded_existing_clients = 0

        for q in search_results:
            origin = q.query_origin if hasattr(q, "query_origin") else q.get("query_origin", "Unknown")
            rs = q.results if hasattr(q, "results") else q.get("results", [])
            for r in rs:
                url = r.get("url")
                title = r.get("title", "")
                if url:
                    domain = extract_domain(url)
                    if domain not in seen_domains:
                        # 1. Existing Client Exclusion
                        if domain in client_domains or any(name in title.lower() for name in client_names):
                            excluded_existing_clients += 1
                            seen_domains.add(domain)
                            continue

                        # 2. Known chain exclusion (FREE — no API call)
                        # But first: check marketplace allowlist (own-brand labels on marketplace domains)
                        if is_known_chain(url, title) and not is_allowlisted_marketplace(url):
                            excluded_chains += 1
                            seen_domains.add(domain)
                            continue
                        
                        # RGPD Suppression check
                        if await is_domain_suppressed(domain):
                            seen_domains.add(domain)
                            continue

                        seen_domains.add(domain)
                        norm_url = normalize_url(url)
                        url_to_origin[norm_url] = origin
                        candidate_urls.append(url)

        if excluded_existing_clients > 0:
            logger.info("│ Phase 0: %d existing Lança clients excluded", excluded_existing_clients)
            new_progress.append(f"🤝 {excluded_existing_clients} parceiros atuais (clientes Lança) omitidos da prospecção")

        if excluded_chains > 0:
            logger.info("│ Phase 0: %d known chains excluded", excluded_chains)
            new_progress.append(f"🛡️ {excluded_chains} cadeias conhecidas excluídas automaticamente")

        pre_filter_count = len(candidate_urls)
        candidate_urls = [u for u in candidate_urls if not is_blog_or_media(u)]
        blogs_filtered = pre_filter_count - len(candidate_urls)
        if blogs_filtered > 0:
            logger.info("│ Phase 0: %d blogs/media filtered out", blogs_filtered)
            new_progress.append(f"📰 {blogs_filtered} blogs/media/marketplaces filtrados")

        logger.info("│ Phase 0 complete: %d candidate URLs after all filters", len(candidate_urls))
        stage_log("phase0_free_filters", target_city,
                  candidates_in=pre_filter_count + excluded_chains + excluded_existing_clients,
                  candidates_out=len(candidate_urls),
                  excluded_chains=excluded_chains,
                  excluded_blogs=blogs_filtered,
                  excluded_existing_clients=excluded_existing_clients)
        logger.debug("[stage=phase0_free_filters] [city=%s] [domains=%s]",
                     target_city, ",".join(urlparse(u).netloc for u in candidate_urls[:50]))
        new_progress.append(
            f"\n🚜 HARVEST: {len(candidate_urls)} URLs únicos encontrados..."
        )

        # Cap candidates intelligently (Priority by origin + sorting instead of random)
        MAX_CANDIDATES = 200
        if len(candidate_urls) > MAX_CANDIDATES:
            # Origin Priority Map
            ORIGIN_PRIORITY = {
                "B2B/PrivateLabel": 100,
                "Trade": 90,
                "Emerging": 80,
                "Sartorial": 70,
                "Local": 65,
                "Wedding": 60,
                "RTW": 50,
                "Editorial": 30,
                "Catch-all": 10,
                "Unknown": 0
            }
            
            # Sort URLs based on origin priority
            candidate_urls.sort(
                key=lambda u: ORIGIN_PRIORITY.get(url_to_origin.get(normalize_url(u), "Unknown"), 0), 
                reverse=True
            )
            
            # Trim
            candidate_urls = candidate_urls[:MAX_CANDIDATES]
            new_progress.append(
                f"   ⚡ Selecionados {MAX_CANDIDATES} melhores candidatos por prioridade de origem"
            )

        # ================================================================
        # PHASE 0b: EXA TEXT FOR TRIAGE (cheap pre-filter, no scraping)
        # ================================================================
        # Exa text is used ONLY for triage (keyword scoring, pre-filter).
        # Real scraping (Crawl4AI) happens AFTER triage on passed candidates.
        exa_text_map = {}
        for qr in search_results:
            for r in qr.results:
                url = r.get("url", "")
                text = r.get("text", "")
                if url and text and len(text) >= 500:
                    norm = normalize_url(url)
                    if norm not in exa_text_map or len(text) > len(exa_text_map[norm]):
                        exa_text_map[norm] = text

        extracted_contents = []
        exa_hits = 0
        for url in candidate_urls:
            norm = normalize_url(url)
            exa_text = exa_text_map.get(norm, "")
            if exa_text and len(exa_text) >= 500:
                extracted_contents.append(ExtractedContent(url=url, content=exa_text[:15000]))
                exa_hits += 1
            else:
                extracted_contents.append(ExtractedContent(url=url, content=""))

        for ec in extracted_contents:
            norm = normalize_url(ec.url)
            ec.query_origin = url_to_origin.get(norm, "Unknown")

        successful_extractions = [e for e in extracted_contents if e.content]
        logger.info("│ Exa text available for triage: %d/%d URLs", exa_hits, len(candidate_urls))
        new_progress.append(
            f"   ✅ Exa text para triagem: {exa_hits}/{len(candidate_urls)} URLs com texto"
        )

        logger.info("│ Running multi-language keyword scoring...")
        new_progress.append(f"\n🌍 KEYWORD SCORING (multi-idioma)...")
        scored_contents = []
        for item in successful_extractions:
            detected_lang = detect_language(item.content)
            kw_score = calculate_keyword_score(item.content, item.url, detected_lang)
            
            if kw_score >= 1:  # Minimum threshold
                item.quality_score = kw_score
                item.language_detected = detected_lang
                scored_contents.append(item)

        logger.info("│ Keyword scoring: %d relevant (score≥1) out of %d", len(scored_contents), len(successful_extractions))
        new_progress.append(
            f"   📉 Quality Check: {len(scored_contents)} relevantes (score ≥ 1) de {len(successful_extractions)}"
        )

        logger.info("│ Enriching %d sites with price data...", len(scored_contents))
        new_progress.append(
            f"   🕵️ Procurando preços em {len(scored_contents)} sites..."
        )
        enriched_contents = await enrich_content_with_prices(scored_contents)

        # Quick vector similarity check — parallel with semaphore to avoid overload
        embed_semaphore = asyncio.Semaphore(5)
        
        async def compute_similarity(content):
            async with embed_semaphore:
                try:
                    similar = await find_similar_clients(content.content[:4000], n_results=1)
                    return similar[0]["similarity"] if similar else 0
                except Exception:
                    return 0
        
        similarity_tasks = [compute_similarity(c) for c in enriched_contents]
        similarity_scores = await asyncio.gather(*similarity_tasks)
        
        pre_filtered = []
        appointment_only_count = 0
        for idx, content in enumerate(enriched_contents):
            appointment_only = False
            if is_appointment_only(content.content):
                appointment_only_count += 1
                appointment_only = True
            
            price_info = extract_price_from_content(content.content)
            price_eur = price_info.get("avg_price", 0)
            price_confidence = price_info.get("confidence", 0)
            
            # Hard filter: if price is confirmed with HIGH confidence AND below €250, skip
            if price_confidence > 0.75 and 0 < price_eur < 250:
                continue

            # NEW Hard Filter: Upper Bound ($2300 approx €2150)
            # If price is clearly ABOVE our maximum range, skip
            if price_confidence > 0.8 and price_eur > 2500:
                continue

            similarity_score = similarity_scores[idx]

            # Only skip if similarity is very low AND no price signal AND no pricing keywords in content
            has_price_keywords = _has_pricing_keywords(content.content)
            if similarity_score < 40 and price_eur == 0 and content.quality_score < 3 and not has_price_keywords:
                continue

            # Pre-filter score (for sorting only)
            # Brands WITH visible prices get a significant bonus
            price_bonus = 25 if price_eur > 500 else 10 if price_eur > 0 else -5
            temp_score = (
                (similarity_score * 0.5) + 
                (content.quality_score * 4) + 
                price_bonus +
                (10 if price_confidence > 0.5 else 0) -
                (4 if appointment_only else 0)
            )

            pre_filtered.append({
                "content": content, 
                "score": temp_score,
                "price_eur": price_eur,
                "price_confidence": price_confidence,
                "similarity": similarity_score,
            })

        if appointment_only_count > 0:
            new_progress.append(
                f"   📅 {appointment_only_count} sites identificados como 'só por marcação' (penalizados, mas não descartados)"
            )

        pre_filtered.sort(key=lambda x: x["score"], reverse=True)
        # Dynamic cap: take all with keyword_score >= 2, fallback to top 120
        high_kw = [x for x in pre_filtered if x["content"].quality_score >= 2]
        triage_candidates = [x["content"] for x in (high_kw if len(high_kw) >= 40 else pre_filtered[:120])]

        logger.info("│ Pre-filter: %d candidates passed → top %d for triage", len(pre_filtered), len(triage_candidates))
        stage_log("phase0b_keyword_prefilter", target_city,
                  candidates_in=len(enriched_contents),
                  candidates_out=len(triage_candidates),
                  scored_relevant=len(scored_contents),
                  pre_filtered_total=len(pre_filtered))
        new_progress.append(
            f"   📊 Pré-filtro: {len(triage_candidates)} candidatos para triagem"
        )

        # ================================================================
        # PHASE 1: FAST TRIAGE (GPT-5.1-mini, batches of 12)
        # ================================================================
        logger.info("│ ── Phase 1: FAST TRIAGE (%d candidates, GPT-mini, batches of %d) ──",
                    len(triage_candidates), TRIAGE_BATCH_SIZE)
        new_progress.append(
            f"\n⚡ TRIAGE RÁPIDA ({len(triage_candidates)} candidatos, GPT-5.1-mini, batches de {TRIAGE_BATCH_SIZE})..."
        )

        # Run triage in batches of TRIAGE_BATCH_SIZE (parallel across batches)
        triage_batches = [
            triage_candidates[i:i + TRIAGE_BATCH_SIZE]
            for i in range(0, len(triage_candidates), TRIAGE_BATCH_SIZE)
        ]
        batch_tasks = [triage_batch(batch, target_city) for batch in triage_batches]
        batch_results_list = await asyncio.gather(*batch_tasks)
        triage_results = []
        for br in batch_results_list:
            triage_results.extend(br)

        # Filter by triage score >= 5 (lowered to get more brands)
        triage_passed = []
        city_rejected_count = 0
        appointment_rejected_count = 0
        no_price_penalized_count = 0
        for content, result in zip(triage_candidates, triage_results):
            score = result.get("score", 0)
            city_match = result.get("city_match", True)
            is_bespoke_only = result.get("is_bespoke_only", False)
            is_appointment_only_llm = result.get("appointment_only", False)
            prices_visible = result.get("prices_visible", True)
            
            # If triage explicitly says no city match, penalize heavily
            if not city_match:
                score = min(score, 4)  # Cap at 4 if no city presence
                city_rejected_count += 1
            
            # Reduce score for appointment-only brands
            if is_appointment_only_llm:
                appointment_rejected_count += 1
                score -= 2
            
            # Penalize brands without visible prices
            if not prices_visible:
                score -= 1  # Soft penalty — premium boutiques often hide prices
                no_price_penalized_count += 1
                
            if score >= 4 and result.get("is_menswear", True):
                triage_passed.append(content)

        if city_rejected_count > 0:
            new_progress.append(
                f"   🏙️ {city_rejected_count} rejeitados por ausência de lojas em {target_city}"
            )
        if appointment_rejected_count > 0:
            new_progress.append(
                f"   📅 {appointment_rejected_count} penalizados (só por marcação, sem catálogo visível)"
            )
        if no_price_penalized_count > 0:
            new_progress.append(
                f"   💰 {no_price_penalized_count} penalizados (preços não visíveis no site)"
            )
        logger.info("│ Triage results: %d passed (city_rejected=%d, appointment=%d, no_price=%d)",
                    len(triage_passed), city_rejected_count, appointment_rejected_count, no_price_penalized_count)
        stage_log("phase1_llm_triage", target_city,
                  candidates_in=len(triage_candidates),
                  candidates_out=len(triage_passed),
                  city_rejected=city_rejected_count,
                  appointment_penalized=appointment_rejected_count,
                  no_price_penalized=no_price_penalized_count)
        new_progress.append(
            f"   ✅ {len(triage_passed)} passaram a triagem (score ≥ 5/10)"
        )

        if not triage_passed:
            return {
                "potential_brands": [],
                "progress": new_progress + ["🎯 RESULTADO: 0 marcas passaram a triagem"],
            }

        # ================================================================
        # PHASE 1.5: GOOGLE PLACES ENRICHMENT (structured location data)
        # Parallel API calls for all triage-passed candidates.
        # ================================================================
        logger.info("│ ── Phase 1.5: GOOGLE PLACES ENRICHMENT (%d candidates) ──", len(triage_passed))
        new_progress.append(
            f"\n📍 GOOGLE PLACES ({len(triage_passed)} boutiques — lojas, moradas, telefone)..."
        )

        places_sem = asyncio.Semaphore(5)
        async def get_places_data(content: ExtractedContent):
            async with places_sem:
                # Extract a likely brand name from the URL domain or title
                domain = urlparse(content.url).netloc.lower().replace("www.", "")
                brand_guess = domain.split(".")[0].replace("-", " ").replace("_", " ").title()
                return await enrich_with_places(
                    brand_name=brand_guess,
                    city=target_city,
                    country=state.target_country if hasattr(state, "target_country") else state.get("target_country", ""),
                )

        places_results = await asyncio.gather(
            *(get_places_data(c) for c in triage_passed)
        )

        # Attach Places data to each content item as structured_data
        places_enriched = 0
        for i, content in enumerate(triage_passed):
            places_data = places_results[i]
            if places_data and (places_data.get("places_address") or places_data.get("places_store_count", 0) > 0):
                places_enriched += 1
            # Store Places data in structured_data for later use
            existing_sd = content.structured_data or {}
            existing_sd["places"] = places_data
            triage_passed[i] = ExtractedContent(
                url=content.url,
                content=content.content,
                structured_data=existing_sd,
                extraction_method=content.extraction_method,
                quality_score=content.quality_score,
                query_origin=content.query_origin,
                language_detected=content.language_detected,
            )

        logger.info("│ Google Places: %d/%d enriched with location data", places_enriched, len(triage_passed))
        new_progress.append(
            f"   ✅ Google Places: {places_enriched}/{len(triage_passed)} com dados de localização"
        )

        # ================================================================
        # PHASE 2: DEEP ANALYSIS (GPT-5.1, batches of 3, parallel)
        # Uses Exa text (already available) — NO scraping needed.
        # ================================================================
        BATCH_SIZE = 6
        batches = [
            triage_passed[i:i + BATCH_SIZE]
            for i in range(0, len(triage_passed), BATCH_SIZE)
        ]

        logger.info("│ ── Phase 2: DEEP ANALYSIS (%d candidates in %d batches, GPT, parallel) ──", len(triage_passed), len(batches))
        new_progress.append(
            f"\n🧠 ANÁLISE PROFUNDA ({len(triage_passed)} candidatos em {len(batches)} batches, GPT-5.1)..."
        )

        async def run_batch(batch_idx, batch):
            logger.info("│   Batch %d/%d: analyzing %d candidates...", batch_idx + 1, len(batches), len(batch))
            batch_results = await deep_analyze_batch(
                batch, price_threshold_usd, target_city
            )
            logger.info("│   Batch %d/%d: %d brands found", batch_idx + 1, len(batches), len(batch_results))
            return batch_idx, batch_results

        batch_outputs = await asyncio.gather(
            *(run_batch(i, b) for i, b in enumerate(batches))
        )

        all_candidates = []
        for batch_idx, batch_results in sorted(batch_outputs, key=lambda x: x[0]):
            all_candidates.extend(batch_results)
            new_progress.append(
                f"   ✅ Batch {batch_idx + 1}/{len(batches)}: {len(batch_results)} marcas encontradas"
            )

        # ================================================================
        # PHASE 2b: POST-LLM PHYSICAL PRESENCE CLASSIFICATION
        # Soft penalty instead of hard reject. Only reject when there is
        # strong counter-evidence (explicit "online only" + no city match).
        # ================================================================
        city_filtered_candidates = []
        city_rejected = 0
        target_city_lower = (target_city or "").lower()

        for data in all_candidates:
            hq_address = (data.get("headquartersAddress") or "").lower()
            hq_in_city = target_city_lower in hq_address

            store_locs = data.get("storeLocations", []) or []
            locations_text = " ".join(str(loc) for loc in store_locs).lower()
            city_in_locations = target_city_lower in locations_text

            # Classify presence type for hierarchical scoring
            if hq_in_city:
                data["city_presence_type"] = "hq"
            elif city_in_locations:
                data["city_presence_type"] = "store"
            else:
                brand_name = data.get("name", "").lower()
                found_city_evidence = False
                for content in triage_passed:
                    if content.content:
                        content_lower = content.content.lower()
                        if brand_name in content_lower and target_city_lower in content_lower:
                            found_city_evidence = True
                            break

                if found_city_evidence:
                    data["city_presence_type"] = "showroom"
                else:
                    # Check for strong counter-evidence: explicit "online only" + nothing in city
                    desc = (data.get("detailedDescription") or data.get("whySelected") or "").lower()
                    explicit_online = any(kw in desc for kw in ("online only", "e-commerce only", "no physical store"))
                    if explicit_online:
                        city_rejected += 1
                        logger.info("│   Rejected: %s — explicit online-only, no presence in %s",
                                    data.get("name", "?"), target_city)
                        continue
                    data["city_presence_type"] = "ambiguous"
            
            city_filtered_candidates.append(data)
        
        if city_rejected > 0:
            new_progress.append(f"   🏙️ {city_rejected} marcas rejeitadas — sem presença confirmada em {target_city}")
        
        stage_log("phase2_deep_analysis", target_city,
                  candidates_in=len(triage_passed),
                  candidates_out=len(city_filtered_candidates),
                  llm_returned=sum(len(br) for _, br in batch_outputs),
                  city_rejected=city_rejected)
        all_candidates = city_filtered_candidates

        # ================================================================
        # PHASE 2.5: SELECTIVE SCRAPING (top 10-12 only, skip if fields filled)
        # Only scrape to fill null fields: email, founder, store list, sample prices.
        # Skip scraping entirely if email + phone + founder already present.
        # ================================================================
        MAX_SCRAPE = 12
        scrape_candidates = []
        for c in all_candidates[:MAX_SCRAPE]:
            has_email = bool(c.get("contactEmail"))
            has_phone = bool(c.get("contactPhone"))
            has_founder = bool(c.get("contactName"))
            if has_email and has_phone and has_founder:
                logger.debug("│   Skip scraping %s — fields already filled", c.get("name", "?"))
                continue
            scrape_candidates.append(c)

        scrape_urls = [c.get("url", "") for c in scrape_candidates if c.get("url")]

        if scrape_urls:
            logger.info("│ ── Phase 2.5: SELECTIVE SCRAPING (%d candidates, skipped %d already-filled) ──",
                        len(scrape_urls), min(MAX_SCRAPE, len(all_candidates)) - len(scrape_urls))
            new_progress.append(
                f"\n🕷️ SCRAPING SELECTIVO (top {len(scrape_urls)} — emails, imagens, LinkedIn)..."
            )

            scraped_results = await batch_extract_content(scrape_urls)
            scraped_map = {}
            for s in scraped_results:
                norm = normalize_url(s.url)
                scraped_map[norm] = s

            scrape_success = sum(1 for s in scraped_results if s.content)
            logger.info("│ Selective scrape: %d/%d successfully scraped", scrape_success, len(scrape_urls))
            new_progress.append(
                f"   ✅ Scraping: {scrape_success}/{len(scrape_urls)} sites (emails, imagens, LinkedIn)"
            )
        else:
            scraped_map = {}

        # ================================================================
        # PHASE 3: DEDUP + BRAND LEAD CREATION (merge LLM + Places + Scrape)
        # ================================================================
        phase3_in = len(all_candidates)
        seen_domains, seen_names, unique_results = set(), set(), []
        for data in all_candidates:
            url = data.get("url", "")
            domain = get_domain_from_url(url)
            name = data.get("name", "").lower().strip()

            if (
                not url
                or not domain
                or domain in seen_domains
                or any(s in name or name in s for s in seen_names)
            ):
                continue

            seen_domains.add(domain)
            seen_names.add(name)

            content_obj = next((e for e in triage_passed if e.url == url), None)

            places_data = {}
            if content_obj and content_obj.structured_data:
                places_data = content_obj.structured_data.get("places", {})

            norm_url = normalize_url(url)
            scraped = scraped_map.get(norm_url)
            sd = scraped.structured_data if scraped and scraped.structured_data else {}

            brand_lead = merge_brand_data(
                llm_data=data,
                places_data=places_data,
                scraped_data=sd,
                content_obj=content_obj,
                target_city=target_city,
            )
            unique_results.append(brand_lead)

        # Sort by fit_score descending, then quality_score
        unique_results.sort(
            key=lambda x: (x.fit_score, x.quality_score), reverse=True
        )

        stage_log("phase3_dedup_assembly", target_city,
                  candidates_in=phase3_in,
                  candidates_out=len(unique_results))
        logger.info("│ ── FINAL: %d unique brands selected ──", len(unique_results))
        for b in unique_results:
            logger.info("│   ✓ %s | fit=%d | price=$%.0f | %s", b.name, b.fit_score, b.average_suit_price_usd, b.website_url)
        logger.info("└──────────────────────────────────────────────────")
        new_progress.append(f"\n🏆 {len(unique_results)} MARCAS SELECIONADAS")
        return {
            "potential_brands": unique_results,
            "candidate_urls": [c.url for c in triage_passed],
            "progress": new_progress,
        }
    except Exception as error:
        logger.exception("CRITICAL ERROR in validation node")
        return {"potential_brands": [], "progress": [f"❌ Erro crítico: {error}"]}
