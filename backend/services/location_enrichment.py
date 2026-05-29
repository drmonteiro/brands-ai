"""
Location enrichment: HQ resolution, store locator extraction, merge and validation.
"""

import asyncio
import json
import logging
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urlparse

logger = logging.getLogger("services.location_enrichment")

EXA_MAX_CHARS = 4000
EXA_MAX_CONCURRENT = 5
HQ_LLM_MAX_CONCURRENT = 3


@dataclass
class CityContext:
    """Target city resolved once per pipeline run — no hardcoded alias lists."""
    query: str
    canonical_name: str
    names: List[str]
    country: Optional[str] = None
    equivalence_cache: Dict[str, bool] = field(default_factory=dict)

    @property
    def normalized_names(self) -> Set[str]:
        return {normalize_city_name(n) for n in self.names if n}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "canonical_name": self.canonical_name,
            "names": self.names,
            "country": self.country,
            "equivalence_cache": self.equivalence_cache,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CityContext":
        return cls(
            query=data.get("query", ""),
            canonical_name=data.get("canonical_name", ""),
            names=list(data.get("names") or []),
            country=data.get("country"),
            equivalence_cache=dict(data.get("equivalence_cache") or {}),
        )

    @classmethod
    def fallback(cls, query: str) -> "CityContext":
        """Conservative fallback when LLM resolution fails — query name only."""
        return cls(
            query=query,
            canonical_name=query,
            names=[query] if query else [],
        )


def _strip_accents(text: str) -> str:
    if not text:
        return ""
    return "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    )


def normalize_city_name(city: str) -> str:
    """Lowercase, strip accents and punctuation for comparison."""
    if not city:
        return ""
    s = _strip_accents(city.lower().strip())
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    for suffix in (" city", " centro", " downtown", " centre", " center"):
        if s.endswith(suffix):
            s = s[: -len(suffix)].strip()
    return s


def _alias_set_for(city: str) -> Set[str]:
    """Deprecated — kept for tests; returns normalized name only."""
    norm = normalize_city_name(city)
    return {norm} if norm else set()


def city_name_matches_context(city_name: str, ctx: CityContext) -> bool:
    """True if city_name refers to the target city (exact or LLM-verified equivalence)."""
    norm = normalize_city_name(city_name)
    if not norm or not ctx:
        return False
    if norm in ctx.normalized_names:
        return True
    cached = ctx.equivalence_cache.get(norm)
    if cached is not None:
        return cached
    return norm == normalize_city_name(ctx.query)


def city_in_text(ctx: CityContext, text: str) -> bool:
    """True if the target city name appears in an address or location string."""
    if not ctx or not text:
        return False
    text_norm = normalize_city_name(text)
    if not text_norm:
        return False
    for name in ctx.normalized_names:
        if len(name) >= 3 and re.search(rf"\b{re.escape(name)}\b", text_norm):
            return True
    return False


async def resolve_target_city_context(city_query: str) -> CityContext:
    """Resolve target city names via LLM — one call per pipeline run."""
    if not city_query or not city_query.strip():
        return CityContext.fallback(city_query or "")

    llm = _get_llm("city_context")
    prompt = f"""The user is searching for menswear brands in the city "{city_query}".

Return the standard names for this SAME municipality (English, local language, common alternate spellings).
Only include names that genuinely refer to this exact city — do NOT include nearby cities or regions.
If the query is ambiguous or not a real city, return confidence "unknown".

Return ONLY JSON:
{{
  "canonical_name": "Standard English name",
  "names": ["all valid spellings including local language"],
  "country": "Country name or null",
  "confidence": "high" or "unknown"
}}"""

    try:
        response = await llm.ainvoke(prompt)
        raw = response.content.replace("```json", "").replace("```", "").strip()
        data = json.loads(raw)
        if (data.get("confidence") or "unknown") != "high":
            logger.warning("City context low confidence for '%s' — using query only", city_query)
            return CityContext.fallback(city_query)

        names = list(data.get("names") or [])
        canonical = data.get("canonical_name") or city_query
        if canonical and canonical not in names:
            names.insert(0, canonical)
        if city_query not in names:
            names.append(city_query)

        ctx = CityContext(
            query=city_query,
            canonical_name=canonical,
            names=names,
            country=data.get("country"),
        )
        logger.info(
            "City context for '%s': %s (%d names)",
            city_query, ctx.canonical_name, len(ctx.names),
        )
        return ctx
    except Exception as e:
        logger.warning("City context LLM error for '%s': %s", city_query, e)
        return CityContext.fallback(city_query)


async def batch_check_hq_cities_against_target(
    ctx: CityContext,
    hq_cities: List[str],
) -> CityContext:
    """One LLM call to verify whether HQ cities match the target (no hardcoded aliases)."""
    unknown = []
    for city in hq_cities:
        norm = normalize_city_name(city)
        if not norm or norm in ctx.normalized_names or norm in ctx.equivalence_cache:
            continue
        unknown.append(city)

    if not unknown:
        return ctx

    llm = _get_llm("city_context")
    cities_block = "\n".join(f"- {c}" for c in unknown[:30])
    names_block = ", ".join(ctx.names)

    prompt = f"""Target search city: {ctx.canonical_name} (also known as: {names_block}).

For each city below, answer whether it is the SAME municipality as the target city.
Be strict — nearby cities, suburbs, or different cities with similar names are NOT the same.

Cities to check:
{cities_block}

Return ONLY JSON array:
[{{"city": "exact city from list", "same_as_target": true or false}}]"""

    try:
        response = await llm.ainvoke(prompt)
        raw = response.content.replace("```json", "").replace("```", "").strip()
        results = json.loads(raw)
        if not isinstance(results, list):
            results = [results]
        for item in results:
            city = item.get("city", "")
            norm = normalize_city_name(city)
            if norm:
                ctx.equivalence_cache[norm] = bool(item.get("same_as_target"))
    except Exception as e:
        logger.warning("HQ city equivalence batch error: %s", e)

    return ctx


def brand_has_city_presence(brand: Dict[str, Any], ctx: CityContext) -> bool:
    """True if HQ or a physical address is confirmed in the target city."""
    hq = brand.get("headquarters_city") or ""
    hq_conf = (brand.get("headquarters_confidence") or "unknown").lower().strip()
    if hq and hq_conf in ("verified", "llm_knowledge") and city_name_matches_context(hq, ctx):
        return True

    local = brand.get("local_store_address") or ""
    if city_in_text(ctx, local):
        return True

    store_locations = brand.get("store_locations") or []
    if isinstance(store_locations, str):
        try:
            store_locations = json.loads(store_locations)
        except Exception:
            store_locations = []

    return any(city_in_text(ctx, loc or "") for loc in store_locations)


def should_exclude_brand_for_location(brand: Dict[str, Any], ctx: CityContext) -> bool:
    """
    Exclude brands with no confirmed presence in the target city.
    Unknown HQ without a verified local store in the city is excluded.
    """
    if brand_has_city_presence(brand, ctx):
        return False

    hq = brand.get("headquarters_city") or ""
    hq_conf = (brand.get("headquarters_confidence") or "unknown").lower().strip()

    if hq and hq_conf in ("verified", "llm_knowledge"):
        return not city_name_matches_context(hq, ctx)

    return True


def get_domain_from_url(url: str) -> str:
    """Extract base domain from URL."""
    if not url:
        return ""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return url


def _get_llm(task: str):
    """Lazy import to avoid loading langgraph when testing pure location helpers."""
    from agents.nodes.utils import get_llm_for_task
    return get_llm_for_task(task)


def _normalize_address(addr: str) -> str:
    """Normalize address for deduplication."""
    if not addr:
        return ""
    normalized = addr.lower().strip()
    normalized = re.sub(r"[^\w\s]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized


def _brand_name_matches(place_name: str, brand_name: str) -> bool:
    """Stricter brand name matching for Google Places results."""
    if not place_name or not brand_name:
        return False
    place_lower = place_name.lower().strip()
    brand_lower = brand_name.lower().strip()
    if brand_lower in place_lower or place_lower in brand_lower:
        return True
    brand_tokens = [t for t in re.split(r"\W+", brand_lower) if len(t) > 2]
    if not brand_tokens:
        return False
    return sum(1 for t in brand_tokens if t in place_lower) >= max(1, len(brand_tokens) // 2)


async def exa_domain_search(
    exa,
    brand_name: str,
    website_url: str,
    query_suffix: str,
    max_chars: int = EXA_MAX_CHARS,
    sem: Optional[asyncio.Semaphore] = None,
) -> str:
    """Search Exa on brand domain for specific content."""
    domain = get_domain_from_url(website_url)
    if not domain:
        return ""

    query = f"{brand_name} {query_suffix}"

    async def _search():
        try:
            response = await asyncio.to_thread(
                exa.search,
                query,
                num_results=3,
                type="auto",
                include_domains=[domain.replace("www.", "")],
                contents={"text": {"maxCharacters": max_chars}},
            )
            texts = []
            for result in response.results:
                if hasattr(result, "text") and result.text:
                    texts.append(result.text)
            if texts:
                combined = "\n---\n".join(texts)
                logger.info("  Exa '%s' for %s: %d chars", query_suffix, brand_name, len(combined))
                return combined
        except Exception as e:
            logger.debug("  Exa search failed for %s (%s): %s", brand_name, query_suffix, e)
        return ""

    if sem:
        async with sem:
            return await _search()
    return await _search()


async def exa_price_lookup(
    exa, brand_name: str, website_url: str, sem: Optional[asyncio.Semaphore] = None
) -> str:
    """Search brand domain for suit pricing content."""
    domain = get_domain_from_url(website_url)
    if not domain:
        return ""
    query = f"{brand_name} suits price"

    async def _search(include_domain: bool):
        kwargs = {
            "num_results": 3,
            "type": "auto",
            "contents": {"text": {"maxCharacters": 5000}},
        }
        if include_domain:
            kwargs["include_domains"] = [domain.replace("www.", "")]
        try:
            response = await asyncio.to_thread(exa.search, query, **kwargs)
            texts = [
                r.text for r in response.results
                if hasattr(r, "text") and r.text
            ]
            if texts:
                return "\n---\n".join(texts)
        except Exception as e:
            logger.debug("  Exa price failed for %s (domain=%s): %s", brand_name, include_domain, e)
        return ""

    async def _run():
        text = await _search(True)
        if text:
            return text
        return await _search(False)

    if sem:
        async with sem:
            return await _run()
    return await _run()


async def exa_hq_lookup(exa, brand_name: str, website_url: str, sem: Optional[asyncio.Semaphore] = None) -> str:
    """Search brand domain for HQ/about/contact page content."""
    return await exa_domain_search(
        exa, brand_name, website_url,
        "headquarters about us contact address registered office",
        sem=sem,
    )


async def exa_store_locator_lookup(
    exa, brand_name: str, website_url: str, sem: Optional[asyncio.Semaphore] = None
) -> str:
    """Search brand domain for store locator page content."""
    return await exa_domain_search(
        exa, brand_name, website_url,
        "store locations find a store boutiques shops",
        sem=sem,
    )


async def extract_hq_from_content(brand_name: str, hq_content: str) -> Dict[str, Any]:
    """Extract HQ from Exa about page content — explicit evidence only."""
    if not hq_content or not hq_content.strip():
        return {
            "headquarters_city": None,
            "headquarters_address": None,
            "origin_country": None,
            "headquarters_confidence": "unknown",
        }

    llm = _get_llm("hq_from_content")
    prompt = f"""Extract headquarters information for the menswear brand "{brand_name}" from the content below.

RULES:
- ONLY extract if EXPLICITLY stated (e.g. "based in", "headquartered in", "registered office", "founded in", footer address)
- NEVER guess or infer from store locations
- If no explicit HQ evidence, return null for all fields and confidence "unknown"

CONTENT:
{hq_content[:4000]}

Return ONLY JSON:
{{
  "headquarters_city": "City name or null",
  "headquarters_address": "Full address or null",
  "origin_country": "Country or null",
  "headquarters_confidence": "verified" or "unknown"
}}"""

    try:
        response = await llm.ainvoke(prompt)
        raw = response.content.replace("```json", "").replace("```", "").strip()
        data = json.loads(raw)
        confidence = data.get("headquarters_confidence", "unknown")
        if confidence != "verified" or not data.get("headquarters_city"):
            return {
                "headquarters_city": None,
                "headquarters_address": None,
                "origin_country": data.get("origin_country"),
                "headquarters_confidence": "unknown",
            }
        return {
            "headquarters_city": data.get("headquarters_city"),
            "headquarters_address": data.get("headquarters_address"),
            "origin_country": data.get("origin_country"),
            "headquarters_confidence": "verified",
        }
    except Exception as e:
        logger.warning("HQ extraction LLM error for %s: %s", brand_name, e)
        return {
            "headquarters_city": None,
            "headquarters_address": None,
            "origin_country": None,
            "headquarters_confidence": "unknown",
        }


async def resolve_headquarters_via_llm_batch(brands: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Single LLM call for all brands still missing verified HQ.
    Only accepts confidence \"high\"; stores city only, never address.
    """
    if not brands:
        return []

    llm = _get_llm("hq_batch")
    blocks = []
    for i, b in enumerate(brands):
        blocks.append(
            f"=== BRAND {i + 1} ===\n"
            f"Name: {b.get('name', '?')}\n"
            f"URL: {b.get('website_url', '?')}\n"
            f"Origin country (if known): {b.get('origin_country') or 'unknown'}\n"
            f"Overview: {(b.get('company_overview') or '')[:400]}"
        )

    prompt = f"""For each menswear brand below, state headquarters city ONLY if you are HIGHLY confident from well-known facts.

RULES (critical):
- Wrong location is worse than null — use confidence \"unknown\" when unsure
- HQ is company base, NOT a retail store in another city
- Do NOT infer from domain TLD or target city alone
- headquarters_address must ALWAYS be null
- Only confidence \"high\" may set headquarters_city

BRANDS ({len(brands)}):
{chr(10).join(blocks)}

Return ONLY a JSON array, one object per brand in SAME order:
[{{
  "headquarters_city": "City or null",
  "headquarters_address": null,
  "origin_country": "Country or null",
  "confidence": "high" or "unknown"
}}]"""

    try:
        response = await llm.ainvoke(prompt)
        raw = response.content.replace("```json", "").replace("```", "").strip()
        rows = json.loads(raw)
        if not isinstance(rows, list):
            rows = [rows]
    except Exception as e:
        logger.warning("Batched LLM HQ fallback error: %s", e)
        return brands

    for brand, row in zip(brands, rows):
        confidence = (row.get("confidence") or "unknown").lower().strip()
        city = row.get("headquarters_city")
        if confidence == "high" and city:
            brand["headquarters_city"] = city
            brand["headquarters_address"] = None
            brand["headquarters_confidence"] = "llm_knowledge"
            if row.get("origin_country") and not brand.get("origin_country"):
                brand["origin_country"] = row["origin_country"]
        elif not brand.get("headquarters_confidence"):
            brand["headquarters_confidence"] = "unknown"

    return brands


async def resolve_headquarters_via_llm(
    brand_name: str,
    website_url: str,
    origin_country: Optional[str] = None,
    description: Optional[str] = None,
) -> Dict[str, Any]:
    """Ask Azure LLM for HQ — only when highly confident; never guess."""
    llm = _get_llm("hq_batch")
    domain = get_domain_from_url(website_url)
    context_parts = [f"Website: {website_url or 'unknown'}"]
    if domain:
        context_parts.append(f"Domain: {domain}")
    if origin_country:
        context_parts.append(f"Known origin country: {origin_country}")
    if description:
        context_parts.append(f"Brand description: {description[:300]}")
    context = "\n".join(context_parts)

    prompt = f"""Where is the headquarters (registered office / main atelier) of the menswear brand "{brand_name}"?

{context}

CRITICAL: Wrong location data is worse than no data.
- Only answer if you are HIGHLY confident this is factual, well-known information.
- The HQ is where the company is based — NOT a retail store in another city.
- Do NOT infer HQ from store locations, domain TLD, or country alone.
- For obscure or unidentifiable brands, return confidence "unknown".

Return ONLY JSON:
{{
  "headquarters_city": "City name or null",
  "headquarters_address": null,
  "origin_country": "Country or null",
  "confidence": "high" or "unknown"
}}"""

    try:
        response = await llm.ainvoke(prompt)
        raw = response.content.replace("```json", "").replace("```", "").strip()
        data = json.loads(raw)
        confidence = (data.get("confidence") or "unknown").lower().strip()
        if confidence != "high" or not data.get("headquarters_city"):
            return {
                "headquarters_city": None,
                "headquarters_address": None,
                "origin_country": None,
                "headquarters_confidence": "unknown",
            }
        return {
            "headquarters_city": data.get("headquarters_city"),
            "headquarters_address": None,
            "origin_country": data.get("origin_country"),
            "headquarters_confidence": "llm_knowledge",
        }
    except Exception as e:
        logger.warning("LLM HQ fallback error for %s: %s", brand_name, e)
        return {
            "headquarters_city": None,
            "headquarters_address": None,
            "origin_country": None,
            "headquarters_confidence": "unknown",
        }


async def extract_stores_from_content(brand_name: str, store_content: str) -> Dict[str, Any]:
    """Extract store list from store locator page content."""
    if not store_content or not store_content.strip():
        return {"stores": [], "total_count": None, "confidence": "unknown", "addresses": []}

    llm = _get_llm("store_extract")
    prompt = f"""Extract physical store locations for the menswear brand "{brand_name}" from the content below.

RULES:
- ONLY list stores explicitly mentioned in the content
- NEVER invent or estimate store locations
- If a total count is explicitly stated (e.g. "5 boutiques"), use it for total_count
- If no store list found, return empty stores and confidence "unknown"

CONTENT:
{store_content[:5000]}

Return ONLY JSON:
{{
  "stores": [{{"city": "London", "address": "12 Savile Row, London W1"}}],
  "total_count": 5,
  "confidence": "verified" or "unknown",
  "source_quote": "exact quote from content or null"
}}"""

    try:
        response = await llm.ainvoke(prompt)
        raw = response.content.replace("```json", "").replace("```", "").strip()
        data = json.loads(raw)
        stores = data.get("stores") or []
        addresses = []
        for s in stores:
            if isinstance(s, dict):
                addr = s.get("address") or s.get("city") or ""
                if addr:
                    addresses.append(addr)
            elif isinstance(s, str):
                addresses.append(s)

        confidence = data.get("confidence", "unknown")
        total = data.get("total_count")
        if confidence == "verified" and addresses:
            count = total if total is not None else len(addresses)
            return {
                "stores": stores,
                "total_count": count,
                "confidence": "verified",
                "addresses": addresses,
            }
        return {"stores": [], "total_count": None, "confidence": "unknown", "addresses": []}
    except Exception as e:
        logger.warning("Store extraction LLM error for %s: %s", brand_name, e)
        return {"stores": [], "total_count": None, "confidence": "unknown", "addresses": []}


def merge_store_data(
    site_addresses: List[str],
    site_count: Optional[int],
    site_confidence: str,
    places_addresses: List[str],
    places_count: int,
) -> Dict[str, Any]:
    """
    Merge store data from website (primary) and Google Places (supplementary).
    """
    merged: List[str] = []
    seen = set()

    def _add(addr: str):
        norm = _normalize_address(addr)
        if norm and norm not in seen:
            seen.add(norm)
            merged.append(addr)

    for addr in site_addresses:
        _add(addr)

    for addr in places_addresses:
        _add(addr)

    if site_confidence == "verified" and site_addresses:
        count = site_count if site_count is not None else len(site_addresses)
        if places_count > 0 and places_count > count * 1.5:
            count = max(count, min(places_count, len(merged)))
            confidence = "uncertain"
        else:
            confidence = "verified"
        return {
            "store_count": count,
            "store_locations": merged or site_addresses,
            "store_count_confidence": confidence,
        }

    if places_addresses or places_count > 0:
        count = places_count if places_count > 0 else len(places_addresses)
        if site_count and site_count > 0 and count > 0:
            ratio = abs(count - site_count) / max(count, site_count)
            if ratio > 0.5:
                conservative = min(count, site_count)
                return {
                    "store_count": conservative,
                    "store_locations": merged or places_addresses,
                    "store_count_confidence": "uncertain",
                }
        return {
            "store_count": count,
            "store_locations": merged or places_addresses,
            "store_count_confidence": "estimated",
        }

    return {
        "store_count": 0,
        "store_locations": [],
        "store_count_confidence": "unknown",
    }


def validate_location_data(brand: Dict[str, Any], ctx: CityContext) -> Dict[str, Any]:
    """Validate and set city_presence_type; never keep unverified addresses."""
    hq_city = (brand.get("headquarters_city") or "").strip()
    hq_conf = (brand.get("headquarters_confidence") or "unknown").lower().strip()
    local = brand.get("local_store_address") or ""
    store_locations = brand.get("store_locations") or []
    if isinstance(store_locations, str):
        try:
            store_locations = json.loads(store_locations)
        except Exception:
            store_locations = []

    stores_in_city = any(city_in_text(ctx, loc or "") for loc in store_locations)
    local_in_city = city_in_text(ctx, local)

    if (
        hq_city
        and hq_conf in ("verified", "llm_knowledge")
        and city_name_matches_context(hq_city, ctx)
    ):
        brand["city_presence_type"] = "hq"
    elif local_in_city or stores_in_city:
        brand["city_presence_type"] = "store"
    elif brand.get("made_to_measure") and local_in_city:
        brand["city_presence_type"] = "showroom"
    else:
        brand["city_presence_type"] = "unknown"

    if hq_conf != "verified":
        brand["headquarters_address"] = None

    if not local_in_city:
        brand["local_store_address"] = None

    return brand


async def resolve_headquarters_for_brand(
    exa,
    brand: Dict[str, Any],
    exa_sem: Optional[asyncio.Semaphore] = None,
    llm_sem: Optional[asyncio.Semaphore] = None,
) -> Dict[str, Any]:
    """Full HQ resolution: Exa about page → mandatory Azure LLM when not verified."""
    brand_name = brand.get("name", "")
    website_url = brand.get("website_url", "")

    if brand.get("headquarters_city") and brand.get("headquarters_confidence") == "verified":
        return brand

    if exa is not None:
        hq_content = await exa_hq_lookup(exa, brand_name, website_url, sem=exa_sem)
        if hq_content:
            hq_data = await extract_hq_from_content(brand_name, hq_content)
            if hq_data.get("headquarters_city"):
                brand["headquarters_city"] = hq_data["headquarters_city"]
                brand["headquarters_address"] = hq_data.get("headquarters_address")
                brand["headquarters_confidence"] = hq_data["headquarters_confidence"]
                if hq_data.get("origin_country") and not brand.get("origin_country"):
                    brand["origin_country"] = hq_data["origin_country"]
                return brand

    if brand.get("headquarters_confidence") != "verified":
        logger.info("  Azure LLM HQ lookup: %s", brand_name)

        async def _llm_lookup():
            return await resolve_headquarters_via_llm(
                brand_name,
                website_url,
                origin_country=brand.get("origin_country"),
                description=brand.get("description"),
            )

        if llm_sem:
            async with llm_sem:
                llm_hq = await _llm_lookup()
        else:
            llm_hq = await _llm_lookup()

        if llm_hq.get("headquarters_city"):
            brand["headquarters_city"] = llm_hq["headquarters_city"]
            brand["headquarters_address"] = None
            brand["headquarters_confidence"] = llm_hq["headquarters_confidence"]
            if llm_hq.get("origin_country") and not brand.get("origin_country"):
                brand["origin_country"] = llm_hq["origin_country"]
        elif not brand.get("headquarters_confidence"):
            brand["headquarters_confidence"] = "unknown"

    return brand


async def resolve_stores_for_brand(
    exa,
    brand: Dict[str, Any],
    sem: Optional[asyncio.Semaphore] = None,
) -> Dict[str, Any]:
    """Extract stores from store locator page via Exa + LLM."""
    brand_name = brand.get("name", "")
    website_url = brand.get("website_url", "")

    store_content = await exa_store_locator_lookup(exa, brand_name, website_url, sem=sem)
    if store_content:
        store_data = await extract_stores_from_content(brand_name, store_content)
        brand["_site_store_addresses"] = store_data.get("addresses", [])
        brand["_site_store_count"] = store_data.get("total_count")
        brand["_site_store_confidence"] = store_data.get("confidence", "unknown")
    else:
        brand["_site_store_addresses"] = []
        brand["_site_store_count"] = None
        brand["_site_store_confidence"] = "unknown"

    return brand
