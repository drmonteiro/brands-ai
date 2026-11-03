"""
Node 2: Filter
Takes raw Exa search results and uses a fast LLM (GPT-5-mini) in batch
to classify each brand: is it a men's suit brand/retailer? Remove everything else.
"""

import logging
from typing import List, Dict, Any, Union

from models import ProspectorState
from services.database import save_lead_rejections
from .llm_schemas import FilterVerdict, validate_items
from .utils import ainvoke_json, get_llm
from .pipeline_timing import step_begin, step_end

logger = logging.getLogger("node.filter")

FILTER_BATCH_SIZE = 12
FILTER_CONTENT_EXCERPT_CHARS = 3500


async def _filter_batch(candidates: List[Dict], target_city: str) -> List[Dict]:
    """
    Send a batch of candidates to GPT-5-mini for quick classification.
    Returns only the candidates that sell men's suits.
    """
    llm = get_llm(fast=True)

    candidates_block = "\n\n".join(
        f"--- CANDIDATE {i+1} ---\n"
        f"URL: {c['url']}\n"
        f"TITLE: {c.get('title', '')}\n"
        f"CONTENT (excerpt): {(c.get('text', '') or c.get('highlights', ''))[:FILTER_CONTENT_EXCERPT_CHARS]}"
        for i, c in enumerate(candidates)
    )

    prompt = f"""You are a strict filter for a Portuguese suit manufacturer (Confeções Lança).
We want businesses whose core product is MEN'S SUITS or tailored menswear (fatos de homem / alfaiataria masculina).

CITY: {target_city}

KEEP only if the content shows the business sells:
- Men's suits (complete, two-piece, three-piece) OR has a strong tailoring/sartorial focus
- Independent boutique, tailor shop with a store, or small brand (1-20 stores). Bespoke and made-to-measure are welcome
- Premium menswear where suits or tailoring are clearly a main line

REMOVE if the business is:
- T-shirt, jeans, casual wear, streetwear or sportswear brand, even if it lists a few blazers
- Women's-only fashion, or suit hire/rental only, or uniforms and workwear
- Shirt-only, shoe-only or accessory-only brand
- Blog, magazine, review site, directory or marketplace
- Department store or fast fashion chain (H&M, Zara, etc.)
- Restaurant, hotel, or non-clothing business
- Anything with no evidence of selling suits

CANDIDATES ({len(candidates)} total):
{candidates_block}

TASK: Decide KEEP or REMOVE for each candidate.
Return ONLY a JSON array with one object per candidate, where "i" is the candidate number:
[{{"i": 1, "keep": true/false, "brand_name": "extracted brand name", "reason": "short reason"}}]

Return ONLY the JSON array, no other text."""

    try:
        verdicts = validate_items(FilterVerdict, await ainvoke_json(llm, prompt))
    except Exception as e:
        logger.warning("Filter batch LLM error: %s — keeping candidates for the quality gate", e)
        verdicts = []

    # Matched by number, so one skipped answer can't shift verdicts onto the wrong brand.
    # The gate checks unassessed brands later, so keeping them can't let a bad lead through.
    by_number = {v.i: v for v in verdicts}
    results = []
    for number, candidate in enumerate(candidates, start=1):
        verdict = by_number.get(number)
        results.append({
            "url": candidate["url"],
            "keep": verdict.keep if verdict else True,
            "brand_name": (verdict.brand_name if verdict else "") or candidate.get("title", ""),
            "reason": verdict.reason if verdict else "not assessed",
        })
    return results


async def filter_node(state: Union[ProspectorState, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Node 2: Filter.
    Takes raw Exa results, uses fast LLM to keep only men's suit brands/retailers.
    """
    target_city = state.get("target_city") if isinstance(state, dict) else getattr(state, "target_city", "")
    raw_results = state.get("search_results_raw") if isinstance(state, dict) else getattr(state, "search_results_raw", [])

    t_node = step_begin(logger, "N2_FILTER", target_city,
                        f"Filtrar {len(raw_results)} candidatos — manter só marcas de fatos de homem.")

    progress = [f"🧹 A filtrar {len(raw_results)} marcas — só fatos e alfaiataria masculina…"]

    if not raw_results:
        step_end(logger, "N2_FILTER", target_city, t_node, "sem candidatos")
        return {
            "filtered_brands": [],
            "progress": progress + ["⚠️ Nenhum candidato para filtrar"],
        }

    # Process in batches
    all_filter_results = []
    for batch_start in range(0, len(raw_results), FILTER_BATCH_SIZE):
        batch = raw_results[batch_start:batch_start + FILTER_BATCH_SIZE]
        batch_num = (batch_start // FILTER_BATCH_SIZE) + 1
        total_batches = (len(raw_results) + FILTER_BATCH_SIZE - 1) // FILTER_BATCH_SIZE

        logger.info("Filter batch %d/%d (%d candidates)", batch_num, total_batches, len(batch))

        batch_results = await _filter_batch(batch, target_city)
        all_filter_results.extend(batch_results)

    # Build filtered list: merge LLM classification with original Exa content
    verdict_by_url = {r["url"]: r for r in all_filter_results}
    filtered_brands = []
    rejections = []

    for candidate in raw_results:
        verdict = verdict_by_url.get(candidate["url"], {})
        if verdict.get("keep", True):
            filtered_brands.append({
                "url": candidate["url"],
                "title": candidate.get("title", ""),
                "text": candidate.get("text", ""),
                "highlights": candidate.get("highlights", ""),
                "brand_name": verdict.get("brand_name") or candidate.get("title", ""),
                "filter_reason": verdict.get("reason", ""),
            })
        else:
            rejections.append({
                "url": candidate["url"],
                "name": verdict.get("brand_name") or candidate.get("title", ""),
                "stage": "filter",
                "code": "filter_removed",
                "reason": verdict.get("reason", ""),
            })
            logger.info("  REMOVED: %s — %s", candidate["url"], verdict.get("reason", ""))

    await save_lead_rejections(target_city, rejections)
    kept, removed = len(filtered_brands), len(rejections)

    progress.append(f"✅ {kept} marcas relevantes mantidas ({removed} fora do perfil)")
    logger.info("Filter result: %d kept, %d removed out of %d total",
                kept, removed, len(raw_results))

    step_end(logger, "N2_FILTER", target_city, t_node,
             kept=kept, removed=removed)

    return {
        "filtered_brands": filtered_brands,
        "progress": progress,
    }
