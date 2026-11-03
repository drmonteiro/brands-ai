"""
Node 4: Score + Save
Compares enriched brands against Lança's client base using pgvector similarity
and LLM fit assessment. Calculates final scores and saves top 20 to PostgreSQL.
"""

import asyncio
import logging
import os
from typing import List, Dict, Any, Union

from models import ProspectorState, BrandLead
from services.vector_db import find_similar_clients_batch
from services.brand_facts import save_brand_linkedin_contacts
from services.database import save_lead_rejections, save_prospect, get_existing_urls_for_city
from services.lead_gate import GateDecision, evaluate_lead
from services.linkedin_contacts import simplify_name
from services.linkedin_contacts import attach_linkedin_contacts
from services.runtime_scoring import (
    calculate_city_presence_score,
    compute_runtime_final_score,
)
from services.currency import eur_to_usd, get_eur_usd_rate
from services.location_enrichment import (
    should_exclude_brand_for_location,
    CityContext,
    resolve_target_city_context,
)
from data.lanca_clients import LANCA_CLIENTS
from .llm_schemas import FitAssessment, validate_items
from .utils import ainvoke_json, get_llm_for_task, normalize_url
from .pipeline_timing import step_begin, step_end

logger = logging.getLogger("node.persistence")

# A limit, not a target: a city can return 6 great leads rather than 20 mixed ones.
MAX_OUTPUT_BRANDS = 20
SIMILAR_CLIENTS_COMPARED = 3
SIMILARITY_ATTEMPTS = 3
SIMILARITY_RETRY_DELAY_SEC = 2
# Fraction of brands with embedding failures that marks the whole run as degraded
SIMILARITY_DEGRADED_FAILURE_RATIO = 0.25
FIT_BATCH_SIZE = 8
# Max concurrent LLM fit batches (N4b); 0 = all batches at once
FIT_LLM_BATCH_CONCURRENT = int(os.environ.get("FIT_LLM_BATCH_CONCURRENT", "0"))

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
    llm = get_llm_for_task("fit_assessment")

    brands_block = "\n\n".join(
        f"--- BRAND {i+1} ---\n"
        f"Name: {b.get('name', '?')}\n"
        f"URL: {b.get('website_url', '?')}\n"
        f"Country: {b.get('origin_country', '?')}\n"
        f"Price: €{b.get('avg_suit_price_eur')}\n"
        f"Stores: {b.get('store_count', '?')}\n"
        f"Wool: {b.get('wool_percentage', '?')}\n"
        f"MTM: {b.get('made_to_measure', '?')}\n"
        f"Style: {b.get('brand_style', '?')}\n"
        f"Business: {b.get('business_model', '?')}\n"
        f"Overview: {(b.get('company_overview') or '')[:500]}"
        for i, b in enumerate(brands)
    )

    prompt = f"""You are evaluating menswear brands as potential clients of Confeções Lança, a Portuguese suit manufacturer.

A great lead is at the SAME LEVEL as Lança's current clients: same kind of business, same price positioning, similar scale.
Judge each brand against this table of every current client.

CURRENT LANÇA CLIENTS:
{_client_benchmark_table()}

WHAT THEY HAVE IN COMMON:
- Independent tailors and menswear brands with suits or tailoring at the core, usually under their own label
- Suits mostly €500-€1,000, with a few from €375 up to €1,500
- Usually 1-8 stores, and at most 30

BRANDS TO EVALUATE ({len(brands)} total):
{brands_block}

TASK: For each brand, return:
- fit_score: 0-10. 10 = could be a current client. 7-9 = strong. 4-6 = moderate. 1-3 = poor. 0 = not suitable
- level: "same" (comparable to the clients above), "above" (clearly more luxury or larger), "below" (clearly cheaper or mass market), or "different_category" (not a suit or tailoring business)
- closest_client: the most comparable client from the table, or null
- fit_reason: one sentence in Portuguese saying why, naming what makes it comparable or not

"Price: €None" means the price is unknown. Judge the level from the other evidence and don't assume it's low.

Return ONLY a JSON array, where "i" is the brand number:
[{{"i": 1, "fit_score": 0, "level": "same", "closest_client": "...", "fit_reason": "..."}}]"""

    try:
        assessments = validate_items(FitAssessment, await ainvoke_json(llm, prompt))
    except Exception as e:
        logger.warning("LLM fit assessment error: %s — these brands stay unassessed", e)
        assessments = []

    by_number = {a.i: a for a in assessments}
    results = []
    for number, brand in enumerate(brands, start=1):
        assessment = by_number.get(number)
        results.append({
            "url": brand.get("website_url", ""),
            "fit_score": assessment.fit_score if assessment else 0,
            "client_level": assessment.level if assessment else None,
            "closest_client": assessment.closest_client if assessment else None,
            "fit_reason": assessment.fit_reason if assessment else "",
        })
    return results


def _client_benchmark_table() -> str:
    return "\n".join(
        f"- {c['name']} ({c.get('country', '?')}): {c.get('store_count', '?')} stores, "
        f"suits €{c.get('pvp_suits_eur') or c.get('avg_suit_price_eur') or '?'}, "
        f"{c.get('brand_type', '?')}, {c.get('brand_style', '?')}, {c.get('business_model', '?')}"
        for c in LANCA_CLIENTS
    )


def _similarity_from_matches(matches: List[Dict]) -> float:
    """Average of the closest clients: scores sit in a narrow band, so one match says little."""
    return min(sum(m["similarity"] for m in matches) / len(matches), 100)


async def _find_similar_with_retries(profile_texts: List[str]) -> List[List[Dict]]:
    for attempt in range(1, SIMILARITY_ATTEMPTS + 1):
        try:
            return await find_similar_clients_batch(profile_texts, n_results=SIMILAR_CLIENTS_COMPARED)
        except Exception as e:
            if attempt == SIMILARITY_ATTEMPTS:
                raise
            logger.warning("Similarity attempt %d failed, retrying: %r", attempt, e)
            await asyncio.sleep(SIMILARITY_RETRY_DELAY_SEC)


def _apply_quality_gate(brands: List[Dict]) -> tuple:
    """Splits brands into (accepted, rejections), recording the reason for every rejection."""
    accepted, rejections = [], []
    seen_names = set()
    # Best first, so when one brand was found on several URLs the strongest is kept.
    for brand in sorted(brands, key=lambda b: b.get("final_score", 0), reverse=True):
        decision = evaluate_lead(brand)
        name = simplify_name(brand.get("name") or "")
        if decision.accepted and name in seen_names:
            decision = GateDecision(False, "duplicate_brand", "A mesma marca já foi aceite noutro endereço.")
        if decision.accepted:
            seen_names.add(name)
            accepted.append(brand)
        else:
            rejections.append({
                "url": brand.get("website_url", ""),
                "name": brand.get("name"),
                "stage": "gate",
                "code": decision.code,
                "reason": decision.reason,
            })
            logger.info("  REJECTED %s [%s]: %s", brand.get("name", "?"), decision.code, decision.reason)
    return accepted, rejections


async def _attach_contacts_to_new_leads(top_brands: List[Dict], existing_urls) -> int:
    """
    Look up contacts only for leads about to be saved: filter can pass 80+ brands
    and only the top ones are kept. A failure here must not lose the leads.
    """
    new_leads = [b for b in top_brands if normalize_url(b.get("website_url", "")) not in existing_urls]
    try:
        await attach_linkedin_contacts(new_leads)
        await save_brand_linkedin_contacts(new_leads)
    except Exception as e:
        logger.warning("LinkedIn contact step failed: %r", e)
    return sum(1 for b in new_leads if b.get("linkedin_contacts"))


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
    # Simplified so accents can't hide a client: "GARCÍA MADRID" is client Garcia Madrid.
    lanca_client_names = {simplify_name(c["name"]) for c in LANCA_CLIENTS}
    lanca_client_names.update(simplify_name(c.get("brand_name", "")) for c in LANCA_CLIENTS)
    lanca_client_names.discard("")

    pre_filter_count = len(enriched_brands)
    filtered_out_clients = []
    filtered_out_location = []
    remaining = []

    for brand in enriched_brands:
        brand_name_lower = simplify_name(brand.get("name") or "")

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
    progress.append("🤝 A comparar cada marca com os clientes Lança…")

    similarity_scores = {}
    similar_client_data = {}
    similarity_failure_count = 0

    profile_texts = [_build_profile_text(b) for b in enriched_brands]
    urls = [b.get("website_url", "") for b in enriched_brands]

    try:
        similar_lists = await _find_similar_with_retries(profile_texts)
        if len(similar_lists) != len(enriched_brands):
            raise ValueError(
                f"Similarity batch length mismatch: {len(similar_lists)} vs {len(enriched_brands)}"
            )
        for brand, url, similar in zip(enriched_brands, urls, similar_lists):
            try:
                if similar:
                    similarity_scores[url] = _similarity_from_matches(similar)
                    similar_client_data[url] = similar
                    brand["similarity_failed"] = False
                else:
                    # No clients to compare with is a failure, not an average brand.
                    similarity_scores[url] = 0.0
                    similar_client_data[url] = []
                    brand["similarity_failed"] = True
                    similarity_failure_count += 1
                    logger.error(
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
    except Exception as e:
        logger.error(
            "SIMILARITY_BATCH_FAILED city=%s: %s — marking all brands failed",
            target_city,
            e,
            exc_info=True,
        )
        for brand, url in zip(enriched_brands, urls):
            brand["similarity_failed"] = True
            similarity_failure_count += 1
            similarity_scores[url] = 0.0
            similar_client_data[url] = []
            progress.append(
                f"⚠️ Similaridade falhou: {brand.get('name', '?')} ({type(e).__name__})"
            )
        progress.append(f"⚠️ Similaridade em batch falhou: {type(e).__name__}")

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
        # Saving now would store leads with made-up scores, as past runs silently did.
        raise RuntimeError(
            "Não foi possível comparar as marcas com os clientes atuais. "
            "A pesquisa foi cancelada e nada foi guardado. Tenta novamente."
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

    # --- Phase 2: LLM fit assessment ---
    t_fit = step_begin(logger, "N4b_LLM_FIT", target_city,
                        "Avaliação de fit via LLM.")
    progress.append("🤖 A avaliar o encaixe de cada marca com a Lança…")

    fit_scores: Dict[str, Dict] = {}
    total_fit_batches = (len(enriched_brands) + FIT_BATCH_SIZE - 1) // FIT_BATCH_SIZE
    fit_sem = (
        asyncio.Semaphore(FIT_LLM_BATCH_CONCURRENT)
        if FIT_LLM_BATCH_CONCURRENT > 0
        else None
    )

    async def _run_fit_batch(batch_start: int) -> tuple:
        if fit_sem:
            async with fit_sem:
                return await _run_fit_batch_inner(batch_start)
        return await _run_fit_batch_inner(batch_start)

    async def _run_fit_batch_inner(batch_start: int) -> tuple:
        batch = enriched_brands[batch_start:batch_start + FIT_BATCH_SIZE]
        batch_num = (batch_start // FIT_BATCH_SIZE) + 1
        results = await _llm_fit_assessment(batch, target_city)
        return batch_start, batch_num, results

    fit_batch_starts = list(range(0, len(enriched_brands), FIT_BATCH_SIZE))
    fit_outcomes = await asyncio.gather(*[_run_fit_batch(bs) for bs in fit_batch_starts])
    fit_outcomes.sort(key=lambda x: x[0])
    for _bs, batch_num, fit_results in fit_outcomes:
        for result in fit_results:
            url = result.get("url", "")
            fit_scores[url] = {
                "score": result.get("fit_score", 0),
                "reason": result.get("fit_reason", ""),
                "level": result.get("client_level"),
                "closest_client": result.get("closest_client"),
            }
        logger.info("LLM fit batch %d/%d done", batch_num, total_fit_batches)

    step_end(logger, "N4b_LLM_FIT", target_city, t_fit,
             brands_assessed=len(fit_scores), parallel_batches=total_fit_batches)

    # --- Phase 3: Final score calculation ---
    scored_brands = []

    for brand in enriched_brands:
        url = brand.get("website_url", "")
        sim_score = similarity_scores.get(url, 50.0)
        fit_data = fit_scores.get(url, {"score": 0, "reason": ""})
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

        final_score, price_score, size_score, _fit_pct = compute_runtime_final_score(
            sim_score, llm_fit, price, stores
        )

        brand["final_score"] = final_score
        brand["similarity_score"] = round(sim_score, 2)
        brand["llm_fit_score"] = llm_fit
        brand["llm_fit_reason"] = fit_data["reason"]
        brand["client_level"] = fit_data.get("level")
        brand["closest_client"] = fit_data.get("closest_client")
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
    accepted_brands, rejections = _apply_quality_gate(scored_brands)
    await save_lead_rejections(target_city, rejections)
    progress.append(
        f"✅ {len(accepted_brands)} marcas cumprem o perfil; {len(rejections)} rejeitadas"
    )

    # Confirmed prices first, so a brand with an unknown price never outranks a proven one.
    accepted_brands.sort(
        key=lambda b: (b.get("price_status") == "confirmed", b.get("final_score", 0)),
        reverse=True,
    )
    top_brands = accepted_brands[:MAX_OUTPUT_BRANDS]

    logger.info("Scoring complete. Top %d brands:", len(top_brands))
    for i, b in enumerate(top_brands):
        logger.info("  #%d: %s (score=%.1f, sim=%.1f, fit=%d, price=€%s, stores=%s)",
                     i + 1, b.get("name", "?"), b.get("final_score", 0),
                     b.get("similarity_score", 0), b.get("llm_fit_score", 0),
                     b.get("avg_suit_price_eur", "?"), b.get("store_count", "?"))

    t_contacts = step_begin(logger, "N4b_LINKEDIN_CONTACTS", target_city,
                            f"Procurar decisores no LinkedIn para {len(top_brands)} marcas.")
    progress.append("👤 A procurar decisores no LinkedIn…")
    with_contacts = await _attach_contacts_to_new_leads(top_brands, existing_urls)
    step_end(logger, "N4b_LINKEDIN_CONTACTS", target_city, t_contacts, with_contacts=with_contacts)
    progress.append(f"✅ Contactos LinkedIn encontrados para {with_contacts} marcas")

    # --- Phase 4: Save to PostgreSQL ---
    t_save = step_begin(logger, "N4c_SAVE_DB", target_city,
                         f"Guardar top {len(top_brands)} marcas na base de dados.")
    progress.append(f"🏆 A selecionar e guardar as {len(top_brands)} melhores marcas…")

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
            "contact_name": brand.get("contact_name"),
            "contact_role": brand.get("contact_role"),
            "contact_email": brand.get("contact_email"),
            "contact_phone": brand.get("contact_phone"),
            "contact_linkedin": brand.get("contact_linkedin"),
            "linkedin_contacts": brand.get("linkedin_contacts") or [],
            "linkedin_contacts_checked_at": brand.get("linkedin_contacts_checked_at"),
            "price_status": brand.get("price_status"),
            "price_source_url": brand.get("price_source_url"),
            "price_evidence": brand.get("price_evidence") or [],
            "fit_reason": brand.get("llm_fit_reason"),
            "closest_client": brand.get("closest_client"),
            "core_category": brand.get("core_category"),
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
                    contact_name=prospect_dict.get("contact_name"),
                    contact_role=prospect_dict.get("contact_role"),
                    contact_email=prospect_dict.get("contact_email"),
                    contact_phone=prospect_dict.get("contact_phone"),
                    contact_linkedin=prospect_dict.get("contact_linkedin"),
                    linkedin_contacts=prospect_dict.get("linkedin_contacts"),
                    linkedin_contacts_checked_at=prospect_dict.get("linkedin_contacts_checked_at"),
                    price_status=prospect_dict.get("price_status"),
                    price_source_url=prospect_dict.get("price_source_url"),
                    price_evidence=prospect_dict.get("price_evidence"),
                    fit_reason=prospect_dict.get("fit_reason"),
                    closest_client=prospect_dict.get("closest_client"),
                    core_category=prospect_dict.get("core_category"),
                )
                verified_brands.append(brand_lead)
                logger.info("  SAVED: %s (score=%.1f)", prospect_dict["name"], brand.get("final_score", 0))
        except Exception as e:
            logger.error("  Error saving %s: %s", brand.get("name", "?"), e)

    step_end(logger, "N4c_SAVE_DB", target_city, t_save,
             saved=saved_count, duplicates=duplicate_count)

    logger.info("Guardados %d novos, %d duplicados", saved_count, duplicate_count)
    dup_note = f" ({duplicate_count} já existiam)" if duplicate_count > 0 else ""
    progress.append(
        f"🎯 Concluído: {len(verified_brands)} marcas guardadas para {target_city}{dup_note}"
    )

    step_end(logger, "N4_SCORE_SAVE", target_city, t_node,
             saved=saved_count, duplicates=duplicate_count, output=len(verified_brands))

    return {
        "verified_brands": verified_brands,
        "progress": progress,
        "similarity_degraded": similarity_degraded,
        "similarity_failure_count": similarity_failure_count,
    }
