import logging
import re
from typing import Tuple, Dict, Any, List, Optional
from urllib.parse import urljoin, urlparse
from services.crawl4ai_client import Crawl4AIResponse, Crawl4AIClient
from services.extraction.css_extractor import (
    css_extractor, 
    ExtractedBoutiqueData,
    REASON_NO_PRICES,
    REASON_PRICES_OUT_OF_RANGE,
    REASON_PRICES_TYPE_MISMATCH,
    REASON_NO_STORES,
    REASON_NO_BRAND
)
from services.extraction.llm_extractor import llm_extractor
from services.extraction.email_extractor import (
    extract_emails_from_html,
    get_best_email,
    extract_linkedin_from_html,
    EmailResult,
)

logger = logging.getLogger(__name__)

# ============================================================================
# PRODUCT IMAGE EXTRACTION
# ============================================================================

JUNK_IMAGE_PATTERNS = re.compile(
    r"(logo|icon|favicon|sprite|placeholder|badge|flag|payment|arrow|spinner|loader|"
    r"banner[-_]?ad|pixel|tracking|spacer|social[-_]|facebook|instagram|twitter|tiktok|"
    r"youtube|pinterest|whatsapp|linkedin|1x1|blank\.gif|\.svg$)",
    re.IGNORECASE,
)

PRODUCT_IMAGE_HINTS = re.compile(
    r"(suit|blazer|jacket|trouser|pant|waistcoat|vest|gilet|tuxedo|smoking|"
    r"fato|casaco|calça|colete|abito|giacca|pantalone|costume|veste|"
    r"anzug|sakko|hose|weste|traje|americana|pantalón|chaleco|"
    r"product|collection|catalog|shop|item|detail)",
    re.IGNORECASE,
)


def extract_product_images_from_html(html: str, page_url: str, max_images: int = 5) -> List[str]:
    """
    Extract high-quality product image URLs from cleaned HTML.
    Filters out logos, icons, banners, and keeps only likely product photos.
    """
    if not html:
        return []

    try:
        from selectolax.parser import HTMLParser
        tree = HTMLParser(html)
    except Exception:
        return []

    candidates: List[Dict[str, Any]] = []

    for img in tree.css("img"):
        src = img.attributes.get("src") or img.attributes.get("data-src") or img.attributes.get("data-lazy-src") or ""
        if not src or src.startswith("data:"):
            continue

        abs_url = urljoin(page_url, src)

        if JUNK_IMAGE_PATTERNS.search(abs_url):
            continue

        alt = (img.attributes.get("alt") or "").lower()
        width = img.attributes.get("width") or ""
        height = img.attributes.get("height") or ""

        try:
            w = int(re.sub(r"[^\d]", "", width)) if width else 0
            h = int(re.sub(r"[^\d]", "", height)) if height else 0
        except ValueError:
            w, h = 0, 0

        if (w > 0 and w < 80) or (h > 0 and h < 80):
            continue

        score = 0

        if PRODUCT_IMAGE_HINTS.search(abs_url):
            score += 3
        if PRODUCT_IMAGE_HINTS.search(alt):
            score += 3

        if w >= 300 or h >= 300:
            score += 2
        elif w == 0 and h == 0:
            score += 1

        parent = img.parent
        if parent:
            parent_class = (parent.attributes.get("class") or "").lower()
            parent_id = (parent.attributes.get("id") or "").lower()
            parent_ctx = f"{parent_class} {parent_id}"
            if PRODUCT_IMAGE_HINTS.search(parent_ctx):
                score += 2

        candidates.append({"url": abs_url, "score": score})

    for meta in tree.css('meta[property="og:image"]'):
        content = meta.attributes.get("content") or ""
        if content and not JUNK_IMAGE_PATTERNS.search(content):
            abs_url = urljoin(page_url, content)
            candidates.append({"url": abs_url, "score": 5})

    candidates.sort(key=lambda c: c["score"], reverse=True)

    seen = set()
    unique = []
    for c in candidates:
        url = c["url"]
        domain = urlparse(url).netloc
        if url not in seen and domain:
            seen.add(url)
            unique.append(url)
            if len(unique) >= max_images:
                break

    return unique

REASON_TO_FIELD = {
    REASON_NO_PRICES: "prices",
    REASON_PRICES_OUT_OF_RANGE: "prices",
    REASON_PRICES_TYPE_MISMATCH: "prices",
    REASON_NO_STORES: "store_addresses",
    REASON_NO_BRAND: "brand_name",
}


# ============================================================================
# LLM OUTPUT SANITIZER
# ============================================================================

def sanitize_llm_output(data: ExtractedBoutiqueData) -> ExtractedBoutiqueData:
    """
    Limpa artefactos JSON/código que o gpt-5-mini injeta nos campos.
    Ex: 'Casa Sartorial}{', "Cavani'}", "PRensademoda'}"
    """
    def clean_string(s: Optional[str]) -> Optional[str]:
        if not s:
            return s
        s = re.sub(r"[{}\[\]'`<>]", "", s)
        s = re.sub(r"ExtractedBoutiqueData", "", s, flags=re.IGNORECASE)
        s = re.sub(r"[|\\]", "", s)
        s = re.sub(r"\s+", " ", s)
        s = s.strip(" ,;:")
        if len(s) < 3:
            return None
        return s

    data.brand_name = clean_string(data.brand_name)
    data.owner_name = clean_string(data.owner_name)
    data.owner_role = clean_string(data.owner_role)

    for store in (data.store_addresses or []):
        store.address = clean_string(store.address) or ""
        store.city = clean_string(store.city) or ""
        store.country = clean_string(store.country) or ""

    return data


# ============================================================================
# CSS MERGE (multi-page → single result)
# ============================================================================

def merge_css_extractions(
    extractions: List[Dict[str, Any]],
) -> ExtractedBoutiqueData:
    """
    Funde resultados CSS de múltiplas páginas.
    Preços: agregar e deduplicar.
    Stores: agregar e deduplicar por cidade.
    Brand: primeiro não-vazio ganha (homepage/about priority).
    Owner: primeiro não-vazio ganha.
    """
    all_prices = []
    all_stores = []
    brand = None
    owner_name = None
    owner_role = None
    all_images: List[str] = []
    seen_img_urls: set = set()

    for ext in extractions:
        data: ExtractedBoutiqueData = ext["data"]
        page_type = ext["type"]

        if data.prices:
            all_prices.extend(data.prices)

        if data.store_addresses:
            all_stores.extend(data.store_addresses)

        if data.brand_name and not brand:
            if page_type in ("homepage", "about"):
                brand = data.brand_name

        if data.owner_name and not owner_name:
            owner_name = data.owner_name
            owner_role = data.owner_role

        for img_url in (data.product_images or []):
            if img_url not in seen_img_urls:
                seen_img_urls.add(img_url)
                all_images.append(img_url)

    if not brand:
        for ext in extractions:
            if ext["data"].brand_name:
                brand = ext["data"].brand_name
                break

    seen_prices: set = set()
    unique_prices = []
    for p in all_prices:
        key = (p.value, p.currency)
        if key not in seen_prices:
            seen_prices.add(key)
            unique_prices.append(p)

    seen_cities: set = set()
    unique_stores = []
    for s in all_stores:
        key = (s.city.lower(), s.country.lower(), s.address[:10].lower() if s.address else "")
        if key not in seen_cities:
            seen_cities.add(key)
            unique_stores.append(s)

    return ExtractedBoutiqueData(
        prices=unique_prices,
        store_addresses=unique_stores,
        brand_name=brand,
        owner_name=owner_name,
        owner_role=owner_role,
        price_source="css",
        product_images=all_images[:5],
    )


# ============================================================================
# COMBINED MARKDOWN BUILDER (for single LLM call)
# ============================================================================

def build_combined_markdown(pages: List[Dict[str, Any]]) -> str:
    """
    Junta markdown de todas as páginas num só bloco,
    com separadores claros para o LLM saber o que é o quê.
    Trunca a 12k chars total.
    """
    sections = []
    for page in pages:
        page_type = page["type"].upper()
        md = page.get("markdown", "")
        if not md or len(md) < 100:
            continue
        sections.append(f"--- {page_type} PAGE ---\n{md}")

    if not sections:
        return ""

    combined = "\n\n".join(sections)

    if len(combined) > 12000:
        combined = _smart_truncate(sections, max_chars=12000)

    return combined


def _smart_truncate(sections: List[str], max_chars: int = 12000) -> str:
    """
    Trunca mantendo homepage e store inteiros (até 4k cada),
    e distribui o resto entre produtos.
    """
    budget = max_chars
    result = []

    priority_sections = [s for s in sections if "HOMEPAGE" in s or "STORE" in s]
    other_sections = [s for s in sections if s not in priority_sections]

    for section in priority_sections:
        truncated = section[:4000]
        result.append(truncated)
        budget -= len(truncated)

    if other_sections and budget > 0:
        per_section = budget // len(other_sections)
        for section in other_sections:
            result.append(section[:per_section])

    return "\n\n".join(result)


# ============================================================================
# MERGE CSS + LLM
# ============================================================================

def merge_extractions(
    css_result: ExtractedBoutiqueData,
    llm_result: ExtractedBoutiqueData,
) -> ExtractedBoutiqueData:
    """
    Funde resultados das duas camadas. Em caso de conflito, prioriza
    CSS (mais determinista) exceto quando CSS tem campo vazio.
    """
    return ExtractedBoutiqueData(
        prices=css_result.prices or llm_result.prices or [],
        store_addresses=(
            css_result.store_addresses
            or llm_result.store_addresses
            or []
        ),
        brand_name=css_result.brand_name or llm_result.brand_name,
        owner_name=llm_result.owner_name or css_result.owner_name,
        owner_role=llm_result.owner_role or css_result.owner_role,
        product_images=css_result.product_images or llm_result.product_images or [],
    )


# ============================================================================
# LINK CLASSIFICATION
# ============================================================================

PRODUCT_KEYWORDS = ["/product", "/shop", "/collection", "/suit", "/blazer", "/jacket", "/tailoring", "/catalog", "/men"]
STORE_KEYWORDS = ["store", "boutique", "location", "find-us", "stockist", "shop-locator", "contact"]


def _classify_internal_links(links: List[str]) -> Dict[str, List[str]]:
    """Classify internal links by page type from a single homepage scrape."""
    product_urls = [u for u in links if any(kw in u.lower() for kw in PRODUCT_KEYWORDS)]
    store_urls = [u for u in links if any(kw in u.lower() for kw in STORE_KEYWORDS)]
    return {"product": product_urls, "store": store_urls}


# ============================================================================
# MAIN FLOW: 1 LLM call per boutique (optimised)
# ============================================================================

async def full_site_extraction_flow(client: Crawl4AIClient, url: str) -> Tuple[ExtractedBoutiqueData, Dict[str, Any], str]:
    """
    Fluxo optimizado com budget de 4 páginas por boutique:
      1 homepage + 2 product + 1 store = 4 max

    Arquitectura:
      FASE 1 — Scrape + CSS extract de cada página (zero LLM)
      FASE 2 — Merge CSS de todas as páginas + quality score
      FASE 3 — SE score < 0.7: 1 única chamada LLM com markdown combinado
      FASE 4 — Juntar contactos, imagens, resultado final
    """
    from urllib.parse import urlparse
    boutique_domain = urlparse(url).netloc.lower().replace("www.", "")

    all_css_extractions: List[Dict[str, Any]] = []
    all_pages: List[Dict[str, Any]] = []
    all_emails: List[EmailResult] = []
    linkedin_url: Optional[str] = None
    homepage_markdown = ""

    # ── FASE 1: Scrape + CSS de todas as páginas ──────────────

    # 1a. Homepage (sempre)
    logger.info(f"[FULL_FLOW] Scraping homepage: {url}")
    homepage_response = await client.scrape(url)

    if not homepage_response.success:
        logger.warning(f"[FULL_FLOW] Homepage scrape failed for {url}")
        return ExtractedBoutiqueData(), {"total_tokens": 0, "cost_usd": 0.0}, ""

    homepage_markdown = homepage_response.best_markdown

    # CSS extract da homepage
    css_result = css_extractor.extract(homepage_response.cleaned_html)
    page_images = extract_product_images_from_html(
        homepage_response.cleaned_html, url, max_images=5
    )
    css_result.product_images = page_images

    all_css_extractions.append({"type": "homepage", "url": url, "data": css_result})
    all_pages.append({"type": "homepage", "url": url, "markdown": homepage_response.best_markdown})

    # Emails + LinkedIn da homepage
    if homepage_response.cleaned_html:
        all_emails.extend(extract_emails_from_html(
            cleaned_html=homepage_response.cleaned_html, domain=boutique_domain,
        ))
        linkedin_url = extract_linkedin_from_html(homepage_response.cleaned_html)

    # 1b. Descobrir links internos
    classified = _classify_internal_links(homepage_response.internal_links)
    pages_to_scrape = {
        "product": classified["product"][:2],
        "store": classified["store"][:1],
    }
    logger.info(
        f"[FULL_FLOW] Links from homepage: "
        f"{len(classified['product'])} product, {len(classified['store'])} store"
    )

    # 1c. Scrape + CSS de sub-páginas (max 3 adicionais)
    scraped_urls = {url}
    for page_type, page_urls in pages_to_scrape.items():
        for page_url in page_urls:
            if page_url in scraped_urls:
                continue
            scraped_urls.add(page_url)

            logger.info(f"[FULL_FLOW] Scraping {page_type}: {page_url}")
            response = await client.scrape(page_url)
            if not response.success:
                logger.warning(f"Falha no scrape de {page_url}")
                continue

            # CSS extract desta página
            css_result = css_extractor.extract(response.cleaned_html)
            page_images = extract_product_images_from_html(
                response.cleaned_html, page_url, max_images=5
            )
            css_result.product_images = page_images

            all_css_extractions.append({"type": page_type, "url": page_url, "data": css_result})
            all_pages.append({"type": page_type, "url": page_url, "markdown": response.best_markdown})

            # Emails + LinkedIn
            if response.cleaned_html:
                all_emails.extend(extract_emails_from_html(
                    cleaned_html=response.cleaned_html, domain=boutique_domain,
                ))
                if not linkedin_url:
                    linkedin_url = extract_linkedin_from_html(response.cleaned_html)

    # ── FASE 2: Merge CSS + quality score ─────────────────────

    merged_css = merge_css_extractions(all_css_extractions)
    score, reasons = css_extractor.extraction_quality_score(merged_css)

    logger.info(
        f"[ORCHESTRATOR] CSS merge de {len(all_pages)} páginas: "
        f"score={score}, reasons={reasons}"
    )

    total_tokens = 0
    total_cost = 0.0

    if score >= 0.7:
        # CSS suficiente — zero chamadas LLM para esta boutique
        logger.info(f"[ORCHESTRATOR] CSS suficiente (score={score}) — LLM não acionado")
        final_result = merged_css
        final_result.price_source = "css"
    else:
        # ── FASE 3: 1 chamada LLM com contexto completo ──────

        combined_markdown = build_combined_markdown(all_pages)

        missing_fields = list({
            REASON_TO_FIELD[r]
            for r in reasons
            if r in REASON_TO_FIELD
        })

        logger.info(
            f"[ORCHESTRATOR] LLM acionado (1 chamada) — "
            f"score={score}, missing={missing_fields}, "
            f"markdown={len(combined_markdown)} chars, "
            f"pages={len(all_pages)}"
        )

        llm_result, token_usage = await llm_extractor.extract(
            markdown=combined_markdown,
            partial_extraction=merged_css,
            missing_fields=missing_fields,
        )

        # Sanitizar output do LLM ANTES do merge
        llm_result = sanitize_llm_output(llm_result)

        total_tokens = token_usage.get("total_tokens", 0)
        total_cost = token_usage.get("cost_usd", 0.0)

        final_result = merge_extractions(merged_css, llm_result)

        if score > 0.3:
            final_result.price_source = "mixed"
        else:
            final_result.price_source = "llm"

    # ── FASE 4: Juntar contactos e imagens ────────────────────

    best_email = get_best_email(all_emails)
    if best_email:
        logger.info(
            f"[EMAIL] {final_result.brand_name or boutique_domain}: "
            f"{best_email.email} (priority={best_email.priority}, source={best_email.source})"
        )
    if linkedin_url:
        logger.info(f"[LINKEDIN] {final_result.brand_name or boutique_domain}: {linkedin_url}")

    if final_result.product_images:
        logger.info(
            f"[IMAGES] Final: {len(final_result.product_images)} product images "
            f"for {final_result.brand_name or boutique_domain}"
        )

    contact_extras = {
        "total_tokens": total_tokens,
        "cost_usd": total_cost,
        "contact_email": best_email.email if best_email else None,
        "email_priority": best_email.priority if best_email else None,
        "email_category": best_email.category if best_email else None,
        "contact_linkedin": linkedin_url,
    }

    return final_result, contact_extras, homepage_markdown
