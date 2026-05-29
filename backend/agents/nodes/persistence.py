"""
Node 4: Score + Save
Compares enriched brands against Lança's client base using pgvector similarity
and LLM fit assessment. Calculates final scores and saves top 20 to PostgreSQL.
"""

import json
import logging
from typing import List, Dict, Any, Union

from models import ProspectorState, BrandLead
from services.vector_db import find_similar_clients
from services.database import save_prospect, get_existing_urls_for_city
from services.scoring import calculate_city_presence_score
from services.currency import eur_to_usd, get_eur_usd_rate
from services.location_enrichment import (
    should_exclude_brand_for_location,
    CityContext,
    resolve_target_city_context,
)
from data.lanca_clients import LANCA_CLIENTS
from .utils import get_llm, normalize_url
from .pipeline_timing import step_begin, step_end

logger = logging.getLogger("node.persistence")

MAX_OUTPUT_BRANDS = 20
# Fraction of brands with embedding failures that marks the whole run as degraded
SIMILARITY_DEGRADED_FAILURE_RATIO = 0.25

# Country name → ISO code for scoring
COUNTRY_TO_CODE = {
    "united kingdom": "GB", "uk": "GB", "england": "GB", "scotland": "GB",
    "france": "FR", "germany": "DE", "italy": "IT", "italia": "IT",
    "spain": "ES", "portugal": "PT", "netherlands": "NL", "belgium": "BE",
    "switzerland": "CH", "sweden": "SE", "denmark": "DK", "norway": "NO",
    "finland": "FI", "ireland": "IE", "austria": "AT", "greece": "GR",
    "united states": "US", "usa": "US", "canada": "CA", "mexico": "MX",
    "brazil": "BR", "colombia": "CO", "peru": "PE", "argentina": "AR",
    "japan": "JP", "china": "CN", "india": "IN", "singapore": "SG",
    "australia": "AU", "south africa": "ZA", "angola": "AO",
    "czech republic": "CZ", "czechia": "CZ", "poland": "PL",
    "uae": "AE", "united arab emirates": "AE", "turkey": "TR",
    "hong kong": "HK", "south korea": "KR", "international": "XX",
}


def _resolve_country_code(country_name: str) -> str:
    if not country_name:
        return "XX"
    return COUNTRY_TO_CODE.get(country_name.lower().strip(), "XX")


def _build_profile_text(brand: Dict) -> str:
    """Build a rich text profile for embedding similarity comparison."""
    parts = [
        f"{brand.get('name', 'Unknown')} is a menswear brand",
    ]
    if brand.get("origin_country"):
        parts.append(f"based in {brand['origin_country']}")
    parts.append(".")

    if brand.get("company_overview"):
        parts.append(brand["company_overview"])

    if brand.get("avg_suit_price_eur"):
        parts.append(f"Suit price: approximately €{brand['avg_suit_price_eur']}.")

    stores = brand.get("store_count", 0)
    if stores:
        parts.append(f"Operates {stores} store(s).")

    if brand.get("wool_percentage"):
        parts.append(f"Wool: {brand['wool_percentage']}.")

    if brand.get("made_to_measure") is True:
        parts.append("Offers made-to-measure services.")

    if brand.get("brand_style"):
        parts.append(f"Style: {brand['brand_style']}.")

    if brand.get("business_model"):
        parts.append(f"Business model: {brand['business_model']}.")

    return " ".join(parts)


async def _llm_fit_assessment(brands: List[Dict], target_city: str) -> List[Dict]:
    """
    Use LLM to assess how well each brand fits as a Lança manufacturing partner.
    Returns list of {url, fit_score (0-10), fit_reason}.
    """
    llm = get_llm(fast=False)

    brands_block = "\n\n".join(
        f"--- BRAND {i+1} ---\n"
        f"Name: {b.get('name', '?')}\n"
        f"URL: {b.get('website_url', '?')}\n"
        f"Country: {b.get('origin_country', '?')}\n"
        f"Price: €{b.get('avg_suit_price_eur', '?')}\n"
        f"Stores: {b.get('store_count', '?')}\n"
        f"Wool: {b.get('wool_percentage', '?')}\n"
        f"MTM: {b.get('made_to_measure', '?')}\n"
        f"Style: {b.get('brand_style', '?')}\n"
        f"Business: {b.get('business_model', '?')}\n"
        f"Overview: {(b.get('company_overview') or '')[:500]}"
        for i, b in enumerate(brands)
    )

    prompt = f"""You are evaluating menswear brands as potential manufacturing partners for Confeções Lança, a Portuguese suit manufacturer.

LANÇA'S IDEAL PARTNER PROFILE:
- Independent menswear retailers/boutiques (NOT large department stores)
- Mid-to-high range: suits €500-€1,700, jackets €300-€1,000
- Fewer than 20 physical stores (easier partnership)
- Brands that value European manufacturing quality
- Own label collections or interested in private label production
- Headquartered or strong presence in {target_city}

CURRENT LANÇA CLIENTS (for reference):
- Hawes & Curtis (UK, 30 stores, €500 suits, 10yr partner)
- Carlos Nieto (Colombia, 20 stores, €800 suits, 12yr partner)
- Walker Slater (UK, 5 stores, €800 suits, Scottish tweed specialist)
- Gresham Blake (UK, 1 store, €1000 suits, bespoke Brighton tailor)
- Garcia Madrid (Spain, 1 store, €1000 suits, 10yr partner)

BRANDS TO EVALUATE ({len(brands)} total):
{brands_block}

TASK: Rate each brand 0-10 on fit as a Lança partner.
10 = perfect match (similar to best current clients)
7-9 = strong fit
4-6 = moderate fit
1-3 = poor fit
0 = not suitable

Return ONLY a JSON array:
[{{"url": "...", "fit_score": 0-10, "fit_reason": "one sentence explanation"}}]"""

    try:
        response = await llm.ainvoke(prompt)
        raw = response.content.replace("```json", "").replace("```", "").strip()
        results = json.loads(raw)
        if not isinstance(results, list):
            results = [results]
        return results
    except Exception as e:
        logger.warning("LLM fit assessment error: %s — defaulting to 5", e)
        return [
            {"url": b.get("website_url", ""), "fit_score": 5, "fit_reason": "assessment error"}
            for b in brands
        ]


async def score_and_save_node(state: Union[ProspectorState, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Node 4: Score + Save.
    1. pgvector similarity against Lança clients
    2. LLM fit assessment
    3. Final score calculation
    4. Save top 20 to PostgreSQL
    """
    target_city = state.get("target_city") if isinstance(state, dict) else getattr(state, "target_city", "")
    enriched_brands = state.get("enriched_brands") if isinstance(state, dict) else getattr(state, "enriched_brands", [])
    exchange_rate = (
        state.get("exchange_rate")
        if isinstance(state, dict)
        else getattr(state, "exchange_rate", None)
    ) or get_eur_usd_rate()

    ctx_data = state.get("target_city_context") if isinstance(state, dict) else getattr(state, "target_city_context", None)
    city_ctx = CityContext.from_dict(ctx_data) if ctx_data else await resolve_target_city_context(target_city)

    t_node = step_begin(logger, "N4_SCORE_SAVE", target_city,
                        f"Scoring + persistência de {len(enriched_brands)} marcas.")

    progress = [f"🎯 Avaliando {len(enriched_brands)} marcas..."]

    if not enriched_brands:
        step_end(logger, "N4_SCORE_SAVE", target_city, t_node, "sem marcas")
        return {
            "verified_brands": [],
            "progress": progress + ["🎯 RESULTADO FINAL: 0 marcas encontradas"],
            "similarity_degraded": False,
            "similarity_failure_count": 0,
        }

    # --- Pre-filter: Exclude existing Lança clients ---
    lanca_client_names = {c["name"].lower().strip() for c in LANCA_CLIENTS}
    lanca_client_names.update(c.get("brand_name", "").lower().strip() for c in LANCA_CLIENTS if c.get("brand_name"))

    pre_filter_count = len(enriched_brands)
    filtered_out_clients = []
    filtered_out_location = []
    remaining = []

    for brand in enriched_brands:
        brand_name_lower = (brand.get("name") or "").lower().strip()

        # Check if this is an existing Lança client (fuzzy: check if client name is contained)
        is_existing_client = False
        for client_name in lanca_client_names:
            if client_name in brand_name_lower or brand_name_lower in client_name:
                is_existing_client = True
                break
        if is_existing_client:
            filtered_out_clients.append(brand.get("name", "?"))
            continue

        # Exclude only when HQ is confidently elsewhere AND no store/HQ in target city
        if should_exclude_brand_for_location(brand, city_ctx):
            hq = brand.get("headquarters_city", "?")
            presence = brand.get("city_presence_type", "unknown")
            filtered_out_location.append(
                f"{brand.get('name', '?')} (HQ: {hq}, presence: {presence})"
            )
            continue

        remaining.append(brand)

    if filtered_out_clients:
        logger.info("Excluded %d existing Lança clients: %s",
                    len(filtered_out_clients), ", ".join(filtered_out_clients))
        progress.append(f"🚫 Excluídos {len(filtered_out_clients)} clientes Lança existentes")

    if filtered_out_location:
        logger.info("Excluded %d brands with no presence in %s: %s",
                    len(filtered_out_location), target_city,
                    ", ".join(filtered_out_location[:10]))
        progress.append(
            f"📍 Excluídas {len(filtered_out_location)} marcas sem presença em {target_city}"
        )

    enriched_brands = remaining
    logger.info("After pre-filters: %d → %d brands", pre_filter_count, len(enriched_brands))

    if not enriched_brands:
        step_end(logger, "N4_SCORE_SAVE", target_city, t_node, "sem marcas após filtros")
        return {
            "verified_brands": [],
            "progress": progress + [f"🎯 RESULTADO FINAL: 0 marcas (todas filtradas)"],
            "similarity_degraded": False,
            "similarity_failure_count": 0,
        }

    existing_urls = await get_existing_urls_for_city(target_city)

    # --- Phase 1: pgvector similarity ---
    t_sim = step_begin(logger, "N4a_SIMILARITY", target_city,
                        "Comparação por embedding com clientes Lança.")
    progress.append("🔗 Calculando similaridade com clientes Lança...")

    similarity_scores = {}
    similar_client_data = {}

    similarity_failure_count = 0

    for brand in enriched_brands:
        url = brand.get("website_url", "")
        profile_text = _build_profile_text(brand)
        try:
            similar = await find_similar_clients(profile_text, n_results=3)
            if similar:
                top_sim = min(similar[0]["similarity"], 100)
                similarity_scores[url] = top_sim
                similar_client_data[url] = similar
                brand["similarity_failed"] = False
            else:
                similarity_scores[url] = 50.0
                similar_client_data[url] = []
                brand["similarity_failed"] = False
                logger.warning(
                    "SIMILARITY_EMPTY brand=%s url=%s (no similar clients returned)",
                    brand.get("name", "?"),
                    url,
                )
        except Exception as e:
            brand["similarity_failed"] = True
            similarity_failure_count += 1
            similarity_scores[url] = 0.0
            similar_client_data[url] = []
            logger.error(
                "SIMILARITY_FAILED brand=%s url=%s: %s",
                brand.get("name", "?"),
                url,
                e,
                exc_info=True,
            )
            progress.append(
                f"⚠️ Similaridade falhou: {brand.get('name', '?')} ({type(e).__name__})"
            )

    total_for_similarity = len(enriched_brands)
    similarity_degraded = (
        total_for_similarity > 0
        and (similarity_failure_count / total_for_similarity) >= SIMILARITY_DEGRADED_FAILURE_RATIO
    )

    if similarity_failure_count:
        progress.append(
            f"⚠️ {similarity_failure_count}/{total_for_similarity} marcas sem similaridade (embedding/pgvector)"
        )
    if similarity_degraded:
        progress.append(
            f"🚨 RUN DEGRADADO: {similarity_failure_count}/{total_for_similarity} falhas de similaridade — "
            "scores de similaridade não são fiáveis nesta execução"
        )
        logger.error(
            "PIPELINE_DEGRADED city=%s similarity_failures=%d/%d",
            target_city,
            similarity_failure_count,
            total_for_similarity,
        )

    step_end(
        logger,
        "N4a_SIMILARITY",
        target_city,
        t_sim,
        brands_compared=len(similarity_scores),
        failures=similarity_failure_count,
        degraded=similarity_degraded,
    )
    progress.append(f"✅ Similaridade calculada para {len(similarity_scores)} marcas")

    # --- Phase 2: LLM fit assessment ---
    t_fit = step_begin(logger, "N4b_LLM_FIT", target_city,
                        "Avaliação de fit via LLM.")
    progress.append("🤖 LLM a avaliar fit de cada marca...")

    # Process in batches of 8
    fit_scores = {}
    FIT_BATCH = 8
    for batch_start in range(0, len(enriched_brands), FIT_BATCH):
        batch = enriched_brands[batch_start:batch_start + FIT_BATCH]
        fit_results = await _llm_fit_assessment(batch, target_city)
        for result in fit_results:
            url = result.get("url", "")
            fit_scores[url] = {
                "score": result.get("fit_score", 5),
                "reason": result.get("fit_reason", ""),
            }

    step_end(logger, "N4b_LLM_FIT", target_city, t_fit,
             brands_assessed=len(fit_scores))
    progress.append(f"✅ LLM fit: {len(fit_scores)} marcas avaliadas")

    # --- Phase 3: Final score calculation ---
    scored_brands = []

    for brand in enriched_brands:
        url = brand.get("website_url", "")
        sim_score = similarity_scores.get(url, 50.0)
        fit_data = fit_scores.get(url, {"score": 5, "reason": ""})
        llm_fit = fit_data["score"]

        price = brand.get("avg_suit_price_eur") or 0
        try:
            price = float(price)
        except (TypeError, ValueError):
            price = 0

        stores = brand.get("store_count") or 0
        try:
            stores = int(stores)
        except (TypeError, ValueError):
            stores = 0

        # Price alignment (0-100): flat max in €500-€1700 range
        if price == 0:
            price_score = 50.0  # neutral for unknown
        elif 500 <= price <= 1700:
            price_score = 100.0
        elif 375 <= price < 500:
            price_score = 30.0 + 70.0 * (price - 375) / 125
        elif 1700 < price <= 2500:
            price_score = 100.0 - 70.0 * (price - 1700) / 800
        else:
            price_score = 10.0

        # Size alignment (0-100): flat max for 1-20 stores
        if stores == 0:
            size_score = 50.0  # neutral for unknown
        elif 1 <= stores <= 20:
            size_score = 100.0
        elif 20 < stores <= 30:
            size_score = 100.0 - 70.0 * (stores - 20) / 10
        else:
            size_score = 10.0

        # Final weighted score (0-100)
        # 40% similarity + 30% LLM fit + 15% price + 15% size
        final_score = (
            0.40 * sim_score +
            0.30 * (llm_fit / 10.0) * 100 +
            0.15 * price_score +
            0.15 * size_score
        )

        brand["final_score"] = round(final_score, 2)
        brand["similarity_score"] = round(sim_score, 2)
        brand["llm_fit_score"] = llm_fit
        brand["llm_fit_reason"] = fit_data["reason"]
        brand["price_score"] = round(price_score, 2)
        brand["size_score"] = round(size_score, 2)

        city_presence = brand.get("city_presence_type", "unknown")
        brand["city_presence_score"] = round(calculate_city_presence_score(city_presence), 2)

        # Store similar client info
        similar = similar_client_data.get(url, [])
        if similar:
            brand["most_similar_client"] = similar[0]["name"]
            brand["similarity_to_best_match"] = similar[0]["similarity"]
        else:
            brand["most_similar_client"] = "N/A"
            brand["similarity_to_best_match"] = 0

        scored_brands.append(brand)

    # Sort by final score descending
    scored_brands.sort(key=lambda b: b.get("final_score", 0), reverse=True)

    # Take top N
    top_brands = scored_brands[:MAX_OUTPUT_BRANDS]

    logger.info("Scoring complete. Top %d brands:", len(top_brands))
    for i, b in enumerate(top_brands):
        logger.info("  #%d: %s (score=%.1f, sim=%.1f, fit=%d, price=€%s, stores=%s)",
                     i + 1, b.get("name", "?"), b.get("final_score", 0),
                     b.get("similarity_score", 0), b.get("llm_fit_score", 0),
                     b.get("avg_suit_price_eur", "?"), b.get("store_count", "?"))

    # --- Phase 4: Save to PostgreSQL ---
    t_save = step_begin(logger, "N4c_SAVE_DB", target_city,
                         f"Guardar top {len(top_brands)} marcas na base de dados.")
    progress.append(f"\n💾 Guardando top {len(top_brands)} marcas...")

    saved_count, duplicate_count = 0, 0
    verified_brands = []

    for brand in top_brands:
        url = brand.get("website_url", "")
        norm_url = normalize_url(url)

        if norm_url in existing_urls:
            duplicate_count += 1
            continue

        country_code = _resolve_country_code(brand.get("origin_country", ""))

        # Build price_note as clean range
        price_min = brand.get("price_range_min_eur")
        price_max = brand.get("price_range_max_eur")
        avg_price = brand.get("avg_suit_price_eur")
        if price_min and price_max and price_min != price_max:
            price_note_str = f"€{int(price_min)} - €{int(price_max)}"
        elif avg_price:
            price_note_str = f"€{int(avg_price)}"
        else:
            price_note_str = None

        prospect_dict = {
            "name": brand.get("name", "Unknown"),
            "website_url": url,
            "city": target_city,
            "country": brand.get("origin_country", "Unknown"),
            "country_code": country_code,
            "store_count": brand.get("store_count", 0),
            "avg_suit_price_eur": float(brand.get("avg_suit_price_eur") or 0),
            "brand_style": brand.get("brand_style", "unknown"),
            "business_model": brand.get("business_model", "unknown"),
            "description": brand.get("company_overview", ""),
            "detailed_description": brand.get("company_overview", ""),
            "store_locations": brand.get("store_locations", []),
            "fit_score": brand.get("llm_fit_score", 0) * 10,
            "material_composition": [brand["wool_percentage"]] if brand.get("wool_percentage") else [],
            "made_to_measure": brand.get("made_to_measure"),
            "wool_percentage": brand.get("wool_percentage"),
            "headquarters_address": brand.get("headquarters_address"),
            "headquarters_city": brand.get("headquarters_city"),
            "headquarters_confidence": brand.get("headquarters_confidence", "unknown"),
            "local_store_address": brand.get("local_store_address"),
            "city_presence_type": brand.get("city_presence_type", "unknown"),
            "store_count_confidence": brand.get("store_count_confidence", "unknown"),
            "price_note": price_note_str,
            "contact_email": brand.get("contact_email"),
            "contact_phone": brand.get("contact_phone"),
        }

        similar = similar_client_data.get(url, [])

        scores = {
            "final_score": brand.get("final_score", 0),
            "passes_hard_filters": True,
            "rejection_reason": None,
            "breakdown": {
                "price_score": brand.get("price_score", 0),
                "size_score": brand.get("size_score", 0),
                "similarity_score": brand.get("similarity_score", 0),
                "quality_score": 0,
                "location_score": 0,
                "wool_score": 0,
                "mtm_score": 0,
                "market_score": 0,
                "city_presence_score": brand.get("city_presence_score", 0),
            },
            "explanation": {
                "price": f"€{prospect_dict['avg_suit_price_eur']:.0f}" if prospect_dict["avg_suit_price_eur"] > 0 else "Unknown",
                "size": f"{prospect_dict['store_count']} stores",
                "most_similar_client": brand.get("most_similar_client", "N/A"),
                "similarity_to_best_match": brand.get("similarity_to_best_match", 0),
                "similarity_explanation": (brand.get("llm_fit_reason", "") or "")[:250],
                "city_presence": brand.get("city_presence_type", "unknown"),
                "wool": brand.get("wool_percentage", "Unknown"),
                "mtm": "Unknown" if brand.get("made_to_measure") is None else ("Yes" if brand.get("made_to_measure") else "No"),
            },
        }

        try:
            result = await save_prospect(
                prospect=prospect_dict,
                city=target_city,
                scores=scores,
                similar_clients=similar,
            )
            if result["status"] == "saved":
                saved_count += 1
                existing_urls.add(norm_url)

                brand_lead = BrandLead(
                    name=prospect_dict["name"],
                    website_url=url,
                    store_count=prospect_dict["store_count"],
                    average_suit_price_usd=eur_to_usd(
                        prospect_dict["avg_suit_price_eur"], exchange_rate
                    ),
                    similarity_failed=brand.get("similarity_failed") or False,
                    city=target_city,
                    origin_country=prospect_dict["country"],
                    avg_suit_price_eur=prospect_dict["avg_suit_price_eur"],
                    fit_score=int(brand.get("final_score", 0)),
                    brand_style=prospect_dict["brand_style"],
                    business_model=prospect_dict["business_model"],
                    company_overview=prospect_dict.get("description"),
                    detailed_description=prospect_dict.get("detailed_description"),
                    store_locations=prospect_dict.get("store_locations", []),
                    wool_percentage=brand.get("wool_percentage"),
                    made_to_measure=brand.get("made_to_measure"),
                    headquarters_address=prospect_dict.get("headquarters_address"),
                    headquarters_city=prospect_dict.get("headquarters_city"),
                    headquarters_confidence=prospect_dict.get("headquarters_confidence"),
                    local_store_address=prospect_dict.get("local_store_address"),
                    city_presence_type=prospect_dict.get("city_presence_type"),
                    store_count_confidence=prospect_dict.get("store_count_confidence"),
                    price_note=price_note_str,
                    contact_email=prospect_dict.get("contact_email"),
                )
                verified_brands.append(brand_lead)
                logger.info("  SAVED: %s (score=%.1f)", prospect_dict["name"], brand.get("final_score", 0))
        except Exception as e:
            logger.error("  Error saving %s: %s", brand.get("name", "?"), e)

    step_end(logger, "N4c_SAVE_DB", target_city, t_save,
             saved=saved_count, duplicates=duplicate_count)

    progress.append(f"  ✅ Guardados: {saved_count} novos")
    if duplicate_count > 0:
        progress.append(f"  ⏭️ Duplicados: {duplicate_count}")
    progress.append(f"\n🎯 RESULTADO FINAL: {len(verified_brands)} marcas encontradas (top {MAX_OUTPUT_BRANDS})")

    step_end(logger, "N4_SCORE_SAVE", target_city, t_node,
             saved=saved_count, duplicates=duplicate_count, output=len(verified_brands))

    return {
        "verified_brands": verified_brands,
        "progress": progress,
        "similarity_degraded": similarity_degraded,
        "similarity_failure_count": similarity_failure_count,
    }
