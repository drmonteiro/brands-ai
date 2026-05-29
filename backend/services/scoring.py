"""
LEGACY rubric scoring (additive 0-100 model aligned with rubric.yaml).

NOT used by the production pipeline. Runtime ranking lives in
``services/runtime_scoring.py`` via ``agents/nodes/persistence.py`` (N4).

Offline evaluation: ``evaluation/rubric_evaluator.py`` + ``rubric.yaml``.
``calculate_prospect_score()`` remains for manual/offline tooling only.

CRITICAL PRINCIPLE (rubric): No hidden preferences inside valid ranges.
  - €500-€2000 suit price → flat maximum (all equally good)
  - 1-20 stores → flat maximum (all equally good)
  - The only hierarchical criterion is city_presence (HQ > store > showroom)

Score components (0-100 total):
  - Price:        0-20 pts (flat inside €500-€2000)
  - Size:         0-15 pts (flat inside 1-20 stores)
  - City Presence: 0-15 pts (hierarchical: HQ > store > showroom)
  - Wool:         0-10 pts (progressive linear)
  - MTM:          0-10 pts (binary bonus)
  - Similarity:   0-20 pts (embedding similarity to Lança clients)
  - Market:       0-10 pts (Lança presence in country)

Hard rejections:
  - Price < €375 → cap score at 40
  - Price > €2500 → REJECT (ultra-luxury red line)
  - Stores > 30 → REJECT (always chain)
"""
import logging
import re
from typing import Dict, List, Optional, Tuple

from data.lanca_clients import MARKET_STRENGTH_STATIC

logger = logging.getLogger("services.scoring")


# ============================================================================
# HARD FILTER THRESHOLDS (from rubric)
# ============================================================================

HARD_FILTER_MIN_PRICE_EUR = 375
HARD_FILTER_MAX_PRICE_EUR = 2500
HARD_FILTER_MAX_STORES = 30

# Rubric valid ranges (flat scoring inside these)
VALID_PRICE_MIN = 500
VALID_PRICE_MAX = 2000
VALID_STORE_MIN = 1
VALID_STORE_MAX = 20

# Kept for backward compat (re-exported to vector_db.py)
IDEAL_PRICE_EUR = 800
IDEAL_MAX_STORES = 4


# ============================================================================
# HARD FILTERS
# ============================================================================

def passes_hard_filters(prospect: Dict) -> Tuple[bool, Optional[str]]:
    """
    Check if prospect passes hard filters per rubric.

    Returns:
        (passes, rejection_reason) — reason is None if passes.
    """
    price = _parse_price(prospect.get("avg_suit_price_eur", 0))
    stores = _parse_int(prospect.get("store_count", 0))

    if price > 0 and price < HARD_FILTER_MIN_PRICE_EUR:
        return False, "price_too_low"

    if price > 0 and price > HARD_FILTER_MAX_PRICE_EUR:
        return False, "price_ultra_luxury"

    if stores > HARD_FILTER_MAX_STORES:
        return False, "too_many_stores"

    return True, None


# ============================================================================
# INDIVIDUAL SCORE COMPONENTS
# ============================================================================

def calculate_price_score(price: float) -> float:
    """
    Suit price score (0-20 pts). FLAT inside €500-€2000.
    No preference for €800 over €500 — rubric says equally good.

    - €500-€2000 → 20 pts (flat max)
    - €375-€500  → linear ramp 5-20
    - €2000-€2500 → linear ramp down 20-5
    - <€375 or >€2500 → 0 (hard filter handles rejection)
    - Unknown (0) → 10 pts (neutral, don't penalize missing data)
    """
    if price == 0 or price is None:
        return 10.0

    if VALID_PRICE_MIN <= price <= VALID_PRICE_MAX:
        return 20.0

    if HARD_FILTER_MIN_PRICE_EUR <= price < VALID_PRICE_MIN:
        return 5.0 + 15.0 * (price - HARD_FILTER_MIN_PRICE_EUR) / (VALID_PRICE_MIN - HARD_FILTER_MIN_PRICE_EUR)

    if VALID_PRICE_MAX < price <= HARD_FILTER_MAX_PRICE_EUR:
        return 20.0 - 15.0 * (price - VALID_PRICE_MAX) / (HARD_FILTER_MAX_PRICE_EUR - VALID_PRICE_MAX)

    return 0.0


def calculate_size_score(store_count: int) -> float:
    """
    Store count score (0-15 pts). FLAT inside 1-20.
    No preference for 1-4 over 5-20 — rubric says equally good.

    - 1-20 stores → 15 pts (flat max)
    - 0 stores (unknown/B2B) → 10 pts (neutral)
    - 21-30 stores → linear ramp down 15-5
    - >30 → 0 (hard filter handles rejection)
    """
    if store_count == 0:
        return 10.0

    if VALID_STORE_MIN <= store_count <= VALID_STORE_MAX:
        return 15.0

    if VALID_STORE_MAX < store_count <= HARD_FILTER_MAX_STORES:
        return 15.0 - 10.0 * (store_count - VALID_STORE_MAX) / (HARD_FILTER_MAX_STORES - VALID_STORE_MAX)

    return 0.0


def calculate_city_presence_score(presence_type: Optional[str]) -> float:
    """
    City presence score (0-15 pts). Hierarchical: HQ > store > showroom.

    - HQ confirmed → 15 pts
    - Store confirmed → 10 pts
    - Showroom / appointment-based → 6 pts
    - Ambiguous → 0 pts (with -10 penalty applied separately)
    - No presence / unknown → 0 pts
    """
    if presence_type is None:
        return 0.0

    p = presence_type.lower().strip()
    if p == "hq":
        return 15.0
    elif p == "store":
        return 10.0
    elif p == "showroom":
        return 6.0
    return 0.0


def calculate_wool_score(wool_percentage) -> float:
    """
    Wool score (0-10 pts). Progressive linear — more wool = better.

    ``None`` or unparseable: 0 bonus points — treated as *unknown*, not as 0%% wool
    (avoids rubric confusion with explicit low-wool garments).
    """
    if wool_percentage is None:
        logger.info(
            "[scoring] wool_percentage=None — 0 wool bonus (unknown, not 0%% wool)"
        )
        return 0.0
    pct = _parse_wool_pct(wool_percentage)
    if pct is None:
        logger.info(
            "[scoring] wool_percentage=%r unparseable — 0 wool bonus (unknown)",
            wool_percentage,
        )
        return 0.0
    return min(10.0, max(0.0, pct / 10.0))


def calculate_mtm_score(made_to_measure) -> float:
    """
    Made-to-measure score (0-10 pts).

    - ``True`` → full bonus (10)
    - ``False`` → partial (3)
    - ``None`` → neutral (5): no bonus, no penalty (LLM ungrounded)
    """
    if made_to_measure is None:
        logger.info("[scoring] made_to_measure=None — neutral MTM score (5.0)")
        return 5.0
    if made_to_measure is True or str(made_to_measure).lower() == "true":
        return 10.0
    elif made_to_measure is False or str(made_to_measure).lower() == "false":
        return 3.0
    return 5.0


def get_market_strength_score(country_code: str) -> float:
    """Market strength score (0-10 pts)."""
    strength = MARKET_STRENGTH_STATIC.get(country_code, 0)
    return min(strength * 0.2, 10.0)


# ============================================================================
# SIMILARITY EXPLANATION (offline / legacy rubric only)
# ============================================================================

async def generate_similarity_explanation(
    prospect: Dict,
    similar_client: Dict,
    similarity_score: float,
) -> str:
    """LLM explanation for rubric tooling — not used by pipeline N4."""
    from config import Config
    from langchain_openai import AzureChatOpenAI

    llm = AzureChatOpenAI(
        azure_endpoint=Config.AZURE_OPENAI_ENDPOINT,
        api_key=Config.AZURE_OPENAI_API_KEY,
        api_version=Config.AZURE_OPENAI_API_VERSION,
        deployment_name=Config.AZURE_OPENAI_DEPLOYMENT,
        temperature=0.3,
    )

    prospect_info = {
        "name": prospect.get("name", "Unknown"),
        "country": prospect.get("country", "Unknown"),
        "store_count": prospect.get("store_count", 0),
        "price_eur": prospect.get("avg_suit_price_eur", 0),
        "wool": prospect.get("wool_percentage", "unknown"),
        "mtm": (
            "unknown"
            if prospect.get("made_to_measure") is None
            else prospect.get("made_to_measure")
        ),
        "style": prospect.get("brand_style", "unknown"),
        "business": prospect.get("business_model", "unknown"),
    }

    client_info = similar_client.get("metadata", {})
    client_profile = similar_client.get("profile", "")

    prompt = f"""You are analyzing why a prospect brand is similar to an existing Confeções Lança client.

PROSPECT:
- Name: {prospect_info['name']}
- Country: {prospect_info['country']}
- Stores: {prospect_info['store_count']}
- Price: €{prospect_info['price_eur']}
- Wool: {prospect_info['wool']}
- Made-to-Measure: {prospect_info['mtm']}
- Style: {prospect_info['style']}
- Business Model: {prospect_info['business']}

LANÇA CLIENT (Most Similar - {similarity_score:.1f}% match):
- Name: {client_info.get('name', 'Unknown')}
- Country: {client_info.get('country', 'Unknown')}
- Stores: {client_info.get('store_count', 0)}
- Wool: {client_info.get('wool_percentage', 'unknown')}
- Made-to-Measure: {client_info.get('made_to_measure', 'unknown')}
- Style: {client_info.get('brand_style', 'unknown')}
- Business Model: {client_info.get('business_model', 'unknown')}
- Profile: {client_profile}

Write a brief explanation (2-3 sentences) in English of why these brands are similar.

Explanation:"""

    try:
        response = await llm.ainvoke(prompt)
        explanation = response.content if hasattr(response, "content") else str(response)
        return explanation.strip()
    except Exception as e:
        logger.warning("Similarity explanation LLM failed: %s", e)
        return (
            f"Similar to {client_info.get('name', 'client')} "
            f"({similarity_score:.1f}% match) based on brand profile and positioning."
        )


# ============================================================================
# MAIN SCORING FUNCTION (legacy rubric — offline only)
# ============================================================================

async def calculate_prospect_score(prospect: Dict) -> Tuple[Dict, List[Dict]]:
    """
    Calculate the final score for a prospect per the Lança Rubric.

    Returns:
        (scores_dict, similar_clients_list)
    """
    from services.vector_db import find_similar_clients, generate_client_profile_text

    passes, rejection_reason = passes_hard_filters(prospect)

    prospect_description = generate_client_profile_text(prospect)
    similar_clients = await find_similar_clients(prospect_description, n_results=5)

    store_count = _parse_int(prospect.get("store_count", 0))
    price = _parse_price(prospect.get("avg_suit_price_eur", 0))
    mtm_raw = prospect.get("made_to_measure", None)
    wool_raw = prospect.get("wool_percentage", None)
    if mtm_raw is None or wool_raw is None:
        logger.info(
            "[scoring] prospect=%s nullable fields: made_to_measure=%s wool_percentage=%s",
            prospect.get("name", "?"),
            repr(mtm_raw),
            repr(wool_raw),
        )

    mtm_score = calculate_mtm_score(mtm_raw)

    # Similarity score (0-20 pts)
    if similar_clients:
        top_similarity = min(similar_clients[0]["similarity"], 100)
        similarity_score = (top_similarity / 100) * 20
    else:
        similarity_score = 10.0

    country_code = prospect.get("country_code", "XX")
    market_score = get_market_strength_score(country_code)

    # LLM Fit Score bonus (0-15 pts, mapped from 0-100 raw)
    llm_raw_fit = prospect.get("fit_score", 0)
    try:
        llm_raw_fit = float(llm_raw_fit)
    except (TypeError, ValueError):
        llm_raw_fit = 0
    fit_score_bonus = (llm_raw_fit / 100) * 15

    # City presence (new hierarchical scoring)
    presence_type = prospect.get("city_presence_type")
    city_presence_score = calculate_city_presence_score(presence_type)

    # Compose final score
    price_pts = calculate_price_score(price)
    size_pts = calculate_size_score(store_count)
    wool_pts = calculate_wool_score(wool_raw)

    final_score = (
        price_pts +            # 0-20 pts
        size_pts +             # 0-15 pts
        city_presence_score +  # 0-15 pts
        wool_pts +             # 0-10 pts
        mtm_score +            # 0-10 pts
        similarity_score +     # 0-20 pts
        market_score           # 0-10 pts
    )
    # Note: fit_score_bonus is additive but total is designed to cap around 100

    if not passes:
        if rejection_reason == "price_ultra_luxury":
            final_score = 0  # full reject
        else:
            final_score = min(final_score, 40)

    most_similar = similar_clients[0] if similar_clients else None

    similarity_explanation = None
    if most_similar:
        try:
            similarity_explanation = await generate_similarity_explanation(
                prospect, most_similar, most_similar["similarity"]
            )
        except Exception as e:
            logger.warning("Could not generate similarity explanation: %s", e)
            similarity_explanation = (
                f"Similar to {most_similar['name']} "
                f"({most_similar['similarity']:.1f}% match) "
                f"based on brand profile and positioning."
            )

    if store_count <= 5:
        size_category = "boutique"
    elif store_count <= 20:
        size_category = "small-medium retailer"
    elif store_count <= 30:
        size_category = "large retailer"
    else:
        size_category = "chain"

    scores = {
        "final_score": round(final_score, 2),
        "passes_hard_filters": passes,
        "rejection_reason": rejection_reason,
        "breakdown": {
            "price_score": round(price_pts, 2),
            "size_score": round(size_pts, 2),
            "city_presence_score": round(city_presence_score, 2),
            "wool_score": round(wool_pts, 2),
            "mtm_score": round(mtm_score, 2),
            "similarity_score": round(similarity_score, 2),
            "market_score": round(market_score, 2),
        },
        "thresholds": {
            "valid_price_range": f"€{VALID_PRICE_MIN}-€{VALID_PRICE_MAX}",
            "hard_reject_price_below": HARD_FILTER_MIN_PRICE_EUR,
            "hard_reject_price_above": HARD_FILTER_MAX_PRICE_EUR,
            "valid_store_range": f"{VALID_STORE_MIN}-{VALID_STORE_MAX}",
            "hard_reject_stores_above": HARD_FILTER_MAX_STORES,
        },
        "explanation": {
            "price": f"€{price:.0f}" if price > 0 else "Unknown",
            "size": f"{store_count} stores → {size_category}",
            "city_presence": presence_type or "unknown",
            "wool": prospect.get("wool_percentage", "Unknown"),
            "mtm": (
                "Unknown"
                if prospect.get("made_to_measure") is None
                else ("Yes" if prospect.get("made_to_measure") else "No")
            ),
            "most_similar_client": most_similar["name"] if most_similar else "N/A",
            "similarity_to_best_match": most_similar["similarity"] if most_similar else 0,
            "similarity_explanation": similarity_explanation,
        },
    }

    return scores, similar_clients


# ============================================================================
# PARSING HELPERS
# ============================================================================

def _parse_price(val) -> float:
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        try:
            return float(val.replace(',', '').replace(' ', ''))
        except (TypeError, ValueError):
            pass
    return 0.0


def _parse_int(val) -> int:
    if isinstance(val, int):
        return val
    if isinstance(val, str):
        try:
            return int(val) if val.isdigit() else 0
        except (TypeError, ValueError):
            pass
    try:
        return int(val)
    except (TypeError, ValueError):
        return 0


def _parse_wool_pct(raw) -> Optional[float]:
    """Extract numeric wool percentage from string like '100%' or 'Pure wool'."""
    if raw is None:
        return None
    s = str(raw).lower()
    m = re.search(r"(\d{1,3})\s*%", s)
    if m:
        return float(m.group(1))
    if "100" in s:
        return 100.0
    if "pure" in s or "pura" in s:
        return 100.0
    if "wool" in s or "lã" in s or "lana" in s or "laine" in s:
        return 50.0
    return None
