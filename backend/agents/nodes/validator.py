"""
Node 3: Validation Node
Data-driven filtering using price extraction, vector similarity, and final LLM analysis.
"""

from typing import List, Dict, Any, Union
import asyncio
import json
import re
from models import ProspectorState, BrandLead, ExtractedContent
from config import CONFECOS_LANCA_PROFILE
from data.premium_locations import detect_premium_location, calculate_location_score
from .utils import get_llm, get_domain_from_url, normalize_url
from services.content_scraper import batch_extract_content, enrich_content_with_prices
from services.price_extractor import extract_price_from_content
from services.vector_db import find_similar_clients
from services.client_analysis import generate_rich_client_examples
from services.database import is_domain_suppressed
from duckduckgo_search import DDGS

# Limit global validation concurrency (e.g., 3 city searches at a time)
validation_semaphore = asyncio.Semaphore(3)


async def validation_node(
    state: Union[ProspectorState, Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Validation Node - "Ruthless" Data-Driven Filtering followed by AI Selection.
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

    print(f"[VALIDATION] Starting validation for {target_city}...")
    new_progress = []

    if not search_results:
        return {
            "potential_brands": [],
            "progress": ["⚠️ Nenhum resultado de busca para processar"],
        }

    try:
        # STEP 1: Aggregate UNIQUE candidates
        candidate_urls = []
        unique_urls = set()
        seen_domains = set()

        for q in search_results:
            for r in q.results:
                url = r.get("url")
                if url:
                    domain = get_domain_from_url(url)
                    if domain not in seen_domains:
                        # [RGPD] Suppression check
                        if await is_domain_suppressed(domain):
                            print(f"[RGPD] Skipping suppressed domain: {domain}")
                            continue

                        seen_domains.add(domain)
                        norm_url = normalize_url(url)
                        if norm_url not in unique_urls:
                            unique_urls.add(norm_url)
                            candidate_urls.append(url)

        new_progress.append(
            f"\n🚜 HARVEST: Processando {len(candidate_urls)} URLs únicos..."
        )
        print(
            f"[VALIDATION] {len(candidate_urls)} candidates after domain/RGPD filtering."
        )

        # STEP 2: SCRAPE EVERYTHING
        extracted_contents = await batch_extract_content(candidate_urls)
        successful_extractions = [e for e in extracted_contents if e.content]
        new_progress.append(
            f"   ✅ Conteúdo extraído: {len(successful_extractions)}/{len(candidate_urls)}"
        )

        # STEP 3: DATA-DRIVEN FILTERING
        new_progress.append(f"\n🛡️ DATA FILTER (Filtro Impiedoso)...")
        keyword_filtered = filter_by_keywords(successful_extractions)
        print(
            f"[VALIDATION] {len(keyword_filtered)} candidates after keyword filtering."
        )
        new_progress.append(f"   📉 Keyword Check: {len(keyword_filtered)} relevantes")

        new_progress.append(
            f"   🕵️ Procurando preços em {len(keyword_filtered)} sites..."
        )
        enriched_contents = await enrich_content_with_prices(keyword_filtered)

        scored_candidates = []
        for content in enriched_contents:
            price_info = extract_price_from_content(content.content)
            price_eur = price_info.get("avg_price", 0)
            if 0 < price_eur < 300:
                continue

            similar_clients = await find_similar_clients(
                content.content[:4000], n_results=1
            )
            similarity_score = (
                similar_clients[0]["similarity"] if similar_clients else 0
            )

            if similarity_score < 45 and price_eur == 0:
                continue

            temp_score = (similarity_score * 0.7) + (30 if price_eur > 500 else 0)
            if temp_score < 25:
                continue

            scored_candidates.append({"content": content, "score": temp_score})

        scored_candidates.sort(key=lambda x: x["score"], reverse=True)
        final_candidates_content = [x["content"] for x in scored_candidates[:25]]

        # STEP 4: LinkedIn Deep Search for Contacts
        new_progress.append(f"\n🔎 Procurando líderes e fundadores no LinkedIn...")

        # Parallel DDG search for each candidate
        async def fetch_linkedin_info(content_obj):
            try:
                domain = get_domain_from_url(content_obj.url)
                # Ensure the domain isn't completely generic
                if len(domain) < 4:
                    return ""

                # Use DuckDuckGo to search for the CEO/Founder on LinkedIn
                query = f"site:linkedin.com/in/ ({domain} OR \"{domain.split('.')[0]}\") (CEO OR Founder OR Owner OR Director OR CFO OR CPO OR Partner OR Buyer OR Manager)"
                results = DDGS().text(query, max_results=3)

                linkedin_context = []
                for res in results:
                    linkedin_context.append(
                        f"Name/Title: {res.get('title', '')} - Profile: {res.get('href', '')} - Bio: {res.get('body', '')}"
                    )

                return "\n".join(linkedin_context)
            except Exception as e:
                print(f"[DDGS] Failed to search LinkedIn for {content_obj.url}: {e}")
                return ""

        # Fetch all linkedin data concurrently
        linkedin_results = await asyncio.gather(
            *(fetch_linkedin_info(obj) for obj in final_candidates_content)
        )

        for i, obj in enumerate(final_candidates_content):
            if linkedin_results[i]:
                obj.content += f"\n\n{'='*40}\n=== LINKEDIN DISCOVERY RESULTS ===\n{linkedin_results[i]}"

        # STEP 5: Final AI Analysis
        new_progress.append(
            f"\n🧠 Análise Final (IA) de {len(final_candidates_content)} finalistas..."
        )
        final_selection = await select_final_candidates(
            final_candidates_content, price_threshold_usd, target_city
        )

        new_progress.append(f"   🏆 {len(final_selection)} MARCAS SELECIONADAS")
        return {
            "potential_brands": final_selection,
            "candidate_urls": [c.url for c in final_candidates_content],
            "progress": new_progress,
        }
    except Exception as error:
        print(f"[VALIDATION] Critical error: {error}")
        return {"potential_brands": [], "progress": [f"❌ Erro crítico: {error}"]}


def filter_by_keywords(contents: List[ExtractedContent]) -> List[ExtractedContent]:
    """Fast directory/irrelevant site filter."""
    pos_kw = [
        "suit",
        "fato",
        "jacket",
        "blazer",
        "tailor",
        "sartorial",
        "bespoke",
        "abito",
        "traje",
        "costume",
        "menswear",
        "moda",
    ]
    neg_kw = [
        "yelp",
        "tripadvisor",
        "directory",
        "pages",
        "list",
        "blog",
        "news",
        "guide",
        "ranking",
    ]

    filtered = []
    for item in contents:
        txt = item.content.lower()[:5000]
        if any(neg in item.url.lower() for neg in neg_kw):
            continue
        score = sum(1 for kw in pos_kw if kw in txt)
        if any(kw in txt for kw in ["suit", "tailor", "bespoke", "sartorial"]):
            score += 3
        if score >= 2:
            filtered.append(item)
    return filtered


async def select_final_candidates(
    extracted_contents: List[ExtractedContent], price_threshold: float, target_city: str
) -> List[BrandLead]:
    """Analyzes and qualifies brands using LLM reasoning."""
    llm = get_llm()
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
    
    CANDIDATES TO EVALUATE:
    {sites_content}
    
    TASK: Return a JSON array of up to 20 brands that are good partnership opportunities.
    LANGUAGE: Use PORTUGUESE (PORTUGAL) for all descriptive text.
    CITY: Must have presence in {target_city}.
    
    CRITICAL RULES:
    1. ENTITY DEDUPLICATION: If two candidates are actually the same brand (even if different URLs or slightly different names), return only the best one.
    2. CONTACT EXTRACTION: Actively search the content for the names of the CEO, Founder, Co-Founder, CFO, CPO, Partner, or Lead Buyer, as well as their email addresses or LinkedIn profiles if available.
    3. SEMANTIC FIT: Evaluate how closely the brand matches the "Golden Profile" of actual Lança clients.
    
    FORMAT:
    [
      {{
        "name": "Brand Name", "url": "URL", "storeCount": int, "isChain": bool,
        "avgPrice": float, "priceSource": "found"|"not_public", "priceNote": "...",
        "woolPercentage": "...", "madeToMeasure": bool, "brandStyle": "...", "businessModel": "...",
        "detailedDescription": "...", "storeLocations": ["..."], "whySelected": "...",
        "city": "{target_city}", "country": "...", "locationQuality": "premium"|"standard",
        "fitScore": int,
        "contactName": "Name of CEO/Founder/CFO/CPO/Partner or null",
        "contactRole": "Exact role (e.g. CEO) or null",
        "contactEmail": "Email address or LinkedIn URL or null",
        "contactPhone": "Mobile/direct phone number or null"
      }}
    ]
    
    CRITICAL DATA POINTS:
    - woolPercentage: Look for labels like "100% Wool", "Pure New Wool", "Super 110s/130s".
    - madeToMeasure: Is there a "Service à medida", "Bespoke", or "Custom Tailoring" option?
    - contactInfo: Extremely valuable. Search for "About Us", "Our Team", "Founder" sections AND carefully check the appended "LINKEDIN DISCOVERY RESULTS" at the very end of the content to find the real CEO/Founder and their LinkedIn URL. 
    
    Return ONLY JSON."""

    try:
        response = await llm.ainvoke(prompt)
        raw = response.content.replace("```json", "").replace("```", "").strip()
        candidates = json.loads(raw)

        seen_domains, seen_names, unique_results = set(), set(), []
        for data in candidates:
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
            content = next((e.content for e in extracted_contents if e.url == url), "")
            street, tier = detect_premium_location(content, target_city)

            location_quality = (
                "premium" if street else data.get("locationQuality", "standard")
            )
            location_score = calculate_location_score(street, tier) if street else 0

            unique_results.append(
                BrandLead(
                    name=data.get("name", "Unknown"),
                    website_url=url,
                    store_count=data.get("storeCount", 1) or 1,
                    average_suit_price_usd=data.get("avgPrice", 0),
                    city=target_city,
                    origin_country=data.get("country", "International"),
                    verified=data.get("priceSource") == "found",
                    brand_style=data.get("brandStyle", "Premium"),
                    business_model=data.get("businessModel", "Retail"),
                    company_overview=data.get("whySelected", ""),
                    detailed_description=data.get("detailedDescription"),
                    store_locations=data.get("storeLocations", []),
                    location_quality=location_quality,
                    location_score=location_score,
                    fit_score=data.get("fitScore", 0),
                    wool_percentage=data.get("woolPercentage"),
                    made_to_measure=data.get("madeToMeasure", False),
                    contact_name=data.get("contactName"),
                    contact_role=data.get("contactRole"),
                    contact_email=data.get("contactEmail"),
                    contact_phone=data.get("contactPhone"),
                    passes_constraints=True,
                )
            )
        return unique_results
    except Exception as e:
        print(f"[SELECTION-AGENT] Error: {e}")
        return []
