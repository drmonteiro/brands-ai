"""
Node 2: Filter
Takes raw Exa search results and uses a fast LLM (GPT-5-mini) in batch
to classify each brand: is it a men's suit brand/retailer? Remove everything else.
"""

import json
import logging
from typing import List, Dict, Any, Union

from models import ProspectorState
from .utils import get_llm
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
We want businesses that sell MEN'S SUITS or tailored menswear (fatos de homem / alfaiataria masculina).

CITY: {target_city}

KEEP if the business sells (even with limited snippet evidence):
- Men's suits (complete, two-piece, three-piece) OR strong tailoring/sartorial focus
- Men's blazers/sport coats and tailored trousers (suit separates)
- Independent boutique, tailor shop with store, or small brand (1-20 stores) — bespoke/MTM is OK
- Formal/premium menswear where suits or tailoring are a core category

REMOVE if the business is:
- T-shirt, casual wear, streetwear, sportswear brand
- Women's-only fashion
- Shirt-only brand (no suits)
- Shoe/accessory-only brand
- Blog, magazine, review site, marketplace
- Generic department store or fast fashion chain (H&M, Zara, etc.)
- Restaurant, hotel, or non-clothing business
- Brand with zero evidence of selling suits

CANDIDATES ({len(candidates)} total):
{candidates_block}

TASK: For each candidate, decide KEEP or REMOVE.
Return ONLY a JSON array with one object per candidate, in SAME order:
[{{"url": "...", "keep": true/false, "brand_name": "extracted brand name", "reason": "short reason"}}]

Return ONLY the JSON array, no other text."""

    try:
        response = await llm.ainvoke(prompt)
        raw = response.content.replace("```json", "").replace("```", "").strip()
        results = json.loads(raw)
        if not isinstance(results, list):
            results = [results]
        return results
    except Exception as e:
        logger.warning("Filter batch LLM error: %s — keeping all candidates as fallback", e)
        return [
            {"url": c["url"], "keep": True, "brand_name": c.get("title", ""), "reason": "filter error fallback"}
            for c in candidates
        ]


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
    filtered_brands = []
    kept, removed = 0, 0

    for i, classification in enumerate(all_filter_results):
        if i >= len(raw_results):
            break

        if classification.get("keep", False):
            kept += 1
            filtered_brands.append({
                "url": raw_results[i]["url"],
                "title": raw_results[i].get("title", ""),
                "text": raw_results[i].get("text", ""),
                "highlights": raw_results[i].get("highlights", ""),
                "brand_name": classification.get("brand_name", raw_results[i].get("title", "")),
                "filter_reason": classification.get("reason", ""),
            })
        else:
            removed += 1
            logger.info("  REMOVED: %s — %s", raw_results[i]["url"], classification.get("reason", ""))

    progress.append(f"✅ {kept} marcas relevantes mantidas ({removed} fora do perfil)")
    logger.info("Filter result: %d kept, %d removed out of %d total",
                kept, removed, len(raw_results))

    step_end(logger, "N2_FILTER", target_city, t_node,
             kept=kept, removed=removed)

    return {
        "filtered_brands": filtered_brands,
        "progress": progress,
    }
