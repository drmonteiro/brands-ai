"""
Node 3: Validation Node V3
2-Phase LLM Analysis: Fast Triage (GPT-5.1-mini) + Deep Analysis (GPT-5.1)
Multi-language keyword scoring, context-aware price extraction, confidence scoring.
"""

from typing import List, Dict, Any, Union, Optional
import asyncio
import json
import re
from models import ProspectorState, BrandLead, ExtractedContent
from config import CONFECOS_LANCA_PROFILE
from data.premium_locations import detect_premium_location, calculate_location_score
from data.multilingual_keywords import (
    calculate_keyword_score,
    is_known_chain,
)
from .utils import get_llm, get_domain_from_url, normalize_url
from services.content_scraper import batch_extract_content, enrich_content_with_prices
from services.price_extractor import extract_price_from_content
from services.vector_db import find_similar_clients
from services.client_analysis import generate_rich_client_examples
from services.database import is_domain_suppressed, extract_domain
from data.lanca_clients import LANCA_CLIENTS

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

async def triage_candidate(content: ExtractedContent, target_city: str) -> Dict[str, Any]:
    """
    Phase 1: Quick triage with fast model. Evaluates one candidate at a time.
    Returns a score 1-10 and basic classification.
    
    Cost: ~$0.01-0.03 per candidate (GPT-5.1-codex-mini with ~3K chars input)
    """
    llm = get_llm(fast=True, temperature=0)
    
    # Only send first 3000 chars — enough for triage, saves tokens
    content_preview = (content.content or "")[:3000]
    
    prompt = f"""You are a quick-filter for a Portuguese suit manufacturer (Confeções Lança) looking for retail partners.

TARGET: Independent boutiques selling mid-to-high range tailored menswear, up to 20 stores.
Price ranges we target:
  - Complete suits (jacket + trousers): $500–$2,300
  - Jackets only: $300–$1,380
  - Trousers only: $200–$920
NOT ultra-luxury/bespoke ateliers — we want brands in the affordable premium/tailoring segment, NOT Savile Row level.
Brands with own label collections or ready-to-wear are a plus.

⚠️ PHYSICAL PRESENCE RULE — READ CAREFULLY:
The brand MUST have a physical store, showroom, or strong retail presence in {target_city}.
If the brand only sells online and has NO physical presence in {target_city}, set city_match to false.

CANDIDATE URL: {content.url}
CONTENT (preview):
{content_preview}

TASK: Rate this as a potential manufacturing partner (1-10) and classify it.

Return ONLY valid JSON:
{{"score": 1-10, "reason": "one short sentence", "is_menswear": true/false, "estimated_price_tier": "budget|mid|premium|luxury|unknown", "estimated_stores": "independent_1_20|chain_20_plus|unknown", "is_chain": true/false, "city_match": true/false, "is_bespoke_only": true/false, "appointment_only": true/false, "prices_visible": true/false}}

SCORING GUIDE:
- 9-10: Perfect match (tailored suits/trousers/waistcoats, within our price ranges, 1-20 stores, own label or RTW, PHYSICAL STORE IN {target_city}, PRICES VISIBLE on website)
- 7-8: Good candidate (mid-high menswear, independent retailer with up to 20 stores, store confirmed in {target_city}, prices visible)
- 5-6: Worth investigating (menswear but unclear on physical locations or price range)
- 3-4: Probably not a match (large chain with >20 stores, wrong segment, ultra-luxury/bespoke only, OR NO physical presence in {target_city})
- 1-2: Definitely not (fast fashion, women only, not retail, not menswear, budget under €250, or clearly NO physical presence in {target_city})

IMPORTANT: If there is NO evidence the brand has a physical store/showroom in {target_city}, set city_match to false and cap score at 4.
IMPORTANT: If the brand is clearly ultra-luxury (suits €3000+, Savile Row bespoke), cap score at 5 — they are above our target range.
IMPORTANT: If the website is APPOINTMENT-ONLY (you must "book an appointment" to see products), DO NOT exclude them, but set appointment_only to true and reduce score by 2.
IMPORTANT: Set prices_visible to true ONLY if actual product prices (€, £, $) are shown on the website. If prices are hidden or "price on request", set to false and REDUCE score by 2 points.
BE INCLUSIVE: If the brand sells any kind of menswear (suits, trousers, waistcoats), is headquartered in {target_city}, and has visible prices, give it at least a score of 5.

Return ONLY JSON."""

    try:
        response = await llm.ainvoke(prompt)
        raw = response.content.replace("```json", "").replace("```", "").strip()
        result = json.loads(raw)
        result["url"] = content.url
        return result
    except Exception as e:
        print(f"[TRIAGE] Error for {content.url}: {e}")
        return {
            "url": content.url,
            "score": 5,  # Neutral — don't exclude on triage failure
            "reason": "triage_failed",
            "is_menswear": True,
            "estimated_price_tier": "unknown",
            "estimated_stores": "unknown",
            "is_chain": False,
            "city_match": True,
        }


# ============================================================================
# PHASE 2: DEEP ANALYSIS (GPT-5.1 — batches of 3)
# ============================================================================

async def deep_analyze_batch(
    extracted_contents: List[ExtractedContent],
    price_threshold_usd: float,
    target_city: str,
) -> List[BrandLead]:
    """
    Phase 2: Deep analysis in small batches of 3.
    Avoids "lost in the middle" problem. Uses GPT-5.1 for maximum quality.
    
    Cost: ~$0.30-0.80 per batch of 3 (GPT-5.1 with ~24K chars input)
    """
    llm = get_llm(fast=False, temperature=0.2)

    sites_content = "\n\n".join(
        [
            f"=== CANDIDATE {i+1} ===\nURL: {e.url}\nCONTENT: {e.content[:8000]}"
            for i, e in enumerate(extracted_contents)
            if e.content
        ]
    )

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

    try:
        response = await llm.ainvoke(prompt)
        raw = response.content.replace("```json", "").replace("```", "").strip()
        candidates = json.loads(raw)
        return candidates
    except Exception as e:
        print(f"[DEEP-ANALYSIS] Error in batch: {e}")
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

    print(f"[VALIDATION V3] Starting 2-phase validation for {target_city}...")
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
                        if is_known_chain(url, title):
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
            new_progress.append(f"🤝 {excluded_existing_clients} parceiros atuais (clientes Lança) omitidos da prospecção")

        if excluded_chains > 0:
            new_progress.append(f"🛡️ {excluded_chains} cadeias conhecidas excluídas automaticamente")

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
        # PHASE 0b: CONTENT EXTRACTION (Exa text → Firecrawl/Jina fallback)
        # ================================================================
        # Build a map of URL → Exa text from search_results (already crawled)
        exa_text_map = {}
        for qr in search_results:
            for r in qr.results:
                url = r.get("url", "")
                text = r.get("text", "")
                if url and text and len(text) >= 500:
                    norm = normalize_url(url)
                    if norm not in exa_text_map or len(text) > len(exa_text_map[norm]):
                        exa_text_map[norm] = text

        # Pre-fill from Exa, identify gaps for Firecrawl/Jina
        extracted_contents = []
        urls_needing_scrape = []
        for url in candidate_urls:
            norm = normalize_url(url)
            exa_text = exa_text_map.get(norm, "")
            if exa_text and len(exa_text) >= 500:
                extracted_contents.append(ExtractedContent(url=url, content=exa_text[:15000]))
            else:
                urls_needing_scrape.append(url)
                extracted_contents.append(ExtractedContent(url=url, content=""))

        exa_hits = len(candidate_urls) - len(urls_needing_scrape)

        # Only call Firecrawl/Jina for URLs that Exa didn't cover
        if urls_needing_scrape:
            scraped = await batch_extract_content(urls_needing_scrape)
            scraped_map = {normalize_url(s.url): s.content for s in scraped if s.content}
            for i, ec in enumerate(extracted_contents):
                if not ec.content:
                    norm = normalize_url(ec.url)
                    if norm in scraped_map:
                        extracted_contents[i] = ExtractedContent(url=ec.url, content=scraped_map[norm])

        for ec in extracted_contents:
            norm = normalize_url(ec.url)
            ec.query_origin = url_to_origin.get(norm, "Unknown")

        successful_extractions = [e for e in extracted_contents if e.content]
        new_progress.append(
            f"   ✅ Conteúdo extraído: {len(successful_extractions)}/{len(candidate_urls)} (Exa: {exa_hits}, Scrape: {len(successful_extractions) - exa_hits})"
        )

        # Multi-language keyword scoring
        new_progress.append(f"\n🌍 KEYWORD SCORING (multi-idioma)...")
        scored_contents = []
        for item in successful_extractions:
            detected_lang = detect_language(item.content)
            kw_score = calculate_keyword_score(item.content, item.url, detected_lang)
            
            if kw_score >= 1:  # Minimum threshold
                item.quality_score = kw_score
                item.language_detected = detected_lang
                scored_contents.append(item)

        new_progress.append(
            f"   📉 Quality Check: {len(scored_contents)} relevantes (score ≥ 1) de {len(successful_extractions)}"
        )

        # Enrich with price data via smart navigation
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

            # Only skip if BOTH similarity is very low AND we have no price signal
            if similarity_score < 40 and price_eur == 0 and content.quality_score < 3:
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
        # Take top 80 for triage (triage is cheap, we want more brands to survive)
        triage_candidates = [x["content"] for x in pre_filtered[:80]]

        new_progress.append(
            f"   📊 Pré-filtro: {len(triage_candidates)} candidatos para triagem"
        )

        # ================================================================
        # PHASE 1: FAST TRIAGE (GPT-5.1-mini, per-candidate)
        # ================================================================
        new_progress.append(
            f"\n⚡ TRIAGE RÁPIDA ({len(triage_candidates)} candidatos, GPT-5.1-mini)..."
        )

        # Run triage in parallel (fast model, individual candidates)
        triage_tasks = [
            triage_candidate(content, target_city)
            for content in triage_candidates
        ]
        triage_results = await asyncio.gather(*triage_tasks)

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
        new_progress.append(
            f"   ✅ {len(triage_passed)} passaram a triagem (score ≥ 5/10)"
        )

        if not triage_passed:
            return {
                "potential_brands": [],
                "progress": new_progress + ["🎯 RESULTADO: 0 marcas passaram a triagem"],
            }

        # ================================================================
        # PHASE 2: DEEP ANALYSIS (GPT-5.1, batches of 3)
        # ================================================================
        BATCH_SIZE = 3
        batches = [
            triage_passed[i:i + BATCH_SIZE]
            for i in range(0, len(triage_passed), BATCH_SIZE)
        ]

        new_progress.append(
            f"\n🧠 ANÁLISE PROFUNDA ({len(triage_passed)} candidatos em {len(batches)} batches, GPT-5.1)..."
        )

        all_candidates = []
        for batch_idx, batch in enumerate(batches):
            batch_results = await deep_analyze_batch(
                batch, price_threshold_usd, target_city
            )
            all_candidates.extend(batch_results)
            new_progress.append(
                f"   ✅ Batch {batch_idx + 1}/{len(batches)}: {len(batch_results)} marcas encontradas"
            )

        # ================================================================
        # PHASE 2b: POST-LLM PHYSICAL PRESENCE VALIDATION
        # ================================================================
        city_filtered_candidates = []
        city_rejected = 0
        target_city_lower = (target_city or "").lower()
        
        for data in all_candidates:
            # Check hasPhysicalPresence flag from LLM
            has_presence = data.get("hasPhysicalPresence", data.get("hasHeadquarters", True))
            
            # Validate address or storeLocations contains the target city
            hq_address = (data.get("headquartersAddress") or "").lower()
            hq_in_city = target_city_lower in hq_address
            
            store_locs = data.get("storeLocations", []) or []
            locations_text = " ".join(str(loc) for loc in store_locs).lower()
            city_in_locations = target_city_lower in locations_text
            
            # Since the LLM is explicitly asked to put "Sede em X (Loja em Y)", 
            # we just ensure they have a store or some city evidence in the triage content
            # if the target city is not explicitly parsed in their locations list.
            if not hq_in_city and not city_in_locations:
                brand_name = data.get("name", "").lower()
                found_city_evidence = False
                for content in triage_passed:
                    if content.content:
                        content_lower = content.content.lower()
                        if brand_name in content_lower and target_city_lower in content_lower:
                            found_city_evidence = True
                            break
                
                if not found_city_evidence:
                    city_rejected += 1
                    print(f"[VALIDATION] Rejected {data.get('name', '?')}: no presence evidence in {target_city}")
                    continue
            
            city_filtered_candidates.append(data)
        
        if city_rejected > 0:
            new_progress.append(f"   🏙️ {city_rejected} marcas rejeitadas — sem presença confirmada em {target_city}")
        
        all_candidates = city_filtered_candidates

        # ================================================================
        # PHASE 3: DEDUP + BRAND LEAD CREATION
        # ================================================================
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

            # Premium Street Detection
            content_obj = next((e for e in triage_passed if e.url == url), None)
            content_text = content_obj.content if content_obj else ""
            street, tier = detect_premium_location(content_text, target_city)

            location_quality = (
                "premium" if street else data.get("locationQuality", "standard")
            )
            location_score = calculate_location_score(street, tier) if street else 0

            unique_results.append(
                BrandLead(
                    name=data.get("name", "Unknown"),
                    website_url=url,
                    store_count=data.get("storeCount", 1) or 1,
                    average_suit_price_usd=data.get("avgPrice") if data.get("avgPrice") is not None else 0,
                    city=target_city,
                    origin_country=data.get("country", "International"),
                    verified=data.get("priceSource") == "found",
                    brand_style=data.get("brandStyle", "Premium"),
                    business_model=data.get("businessModel", "Retail"),
                    company_overview=data.get("whySelected", ""),
                    detailed_description=data.get("detailedDescription"),
                    store_locations=data.get("storeLocations", []) or [],
                    location_quality=location_quality,
                    location_score=location_score,
                    fit_score=data.get("fitScore") if data.get("fitScore") is not None else 0,
                    wool_percentage=data.get("woolPercentage"),
                    made_to_measure=data.get("madeToMeasure", False),
                    contact_name=data.get("contactName"),
                    contact_role=data.get("contactRole"),
                    contact_email=data.get("contactEmail"),
                    contact_phone=data.get("contactPhone"),
                    headquarters_address=data.get("headquartersAddress"),
                    passes_constraints=True,
                    quality_score=getattr(content_obj, "quality_score", 0) if content_obj else 0,
                    query_origin=getattr(content_obj, "query_origin", "Unknown") if content_obj else "Unknown",
                    price_source=data.get("priceSource") or (content_obj.structured_data.get("price_source") if content_obj and content_obj.structured_data else None),
                )
            )

        # Sort by fit_score descending, then quality_score
        unique_results.sort(
            key=lambda x: (x.fit_score, x.quality_score), reverse=True
        )

        new_progress.append(f"\n🏆 {len(unique_results)} MARCAS SELECIONADAS")
        return {
            "potential_brands": unique_results,
            "candidate_urls": [c.url for c in triage_passed],
            "progress": new_progress,
        }
    except Exception as error:
        import traceback
        traceback.print_exc()
        print(f"[VALIDATION V3] Critical error: {error}")
        return {"potential_brands": [], "progress": [f"❌ Erro crítico: {error}"]}
