"""
Extract structured hints from discovery Exa content before supplemental searches.

No LLM — regex/heuristics only. Wrong > empty: only set fields with explicit evidence.
"""

import re
from typing import Any, Dict, List, Optional

from services.currency import CHF_TO_EUR, GBP_TO_EUR, USD_TO_EUR

DISCOVERY_MAX_CHARS = 10_000

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
_EMAIL_BLOCK = ("noreply", "no-reply", "unsubscribe", "mailer-daemon", "privacy@")
_EMAIL_PREFERRED = ("info@", "contact@", "hello@", "sales@", "enquir", "customercare@")

_LINKEDIN_URL_RE = re.compile(
    r"https?://(?:[a-z]{2,3}\.)?linkedin\.com/(?:in|company)/[a-zA-Z0-9\-_%]+/?",
    re.I,
)
_LINKEDIN_BARE_RE = re.compile(
    r"(?:https?://)?(?:www\.)?linkedin\.com/(in|company)/([a-zA-Z0-9\-_%]+)/?",
    re.I,
)

_HQ_PATTERNS = [
    re.compile(
        r"(?:based in|headquartered in|head office in|registered office in|founded in)"
        r"\s+([A-Z][A-Za-zÀ-ÿ\s\-]{2,40}?)(?:,|\s+(?:UK|USA|United|Portugal|Italy|France|Germany)|\.)",
        re.I,
    ),
]

_STORE_COUNT_RE = re.compile(
    r"\b(\d{1,3})\s+(?:stores?|boutiques?|locations?|shops?)\b",
    re.I,
)

_PRICE_PATTERNS = [
    (re.compile(r"€\s*([\d.,]+)"), "EUR", 1.0),
    (re.compile(r"£\s*([\d.,]+)"), "GBP", GBP_TO_EUR),
    (re.compile(r"\$\s*([\d.,]+)"), "USD", USD_TO_EUR),
    (re.compile(r"CHF\s*([\d.,]+)", re.I), "CHF", CHF_TO_EUR),
    (re.compile(r"([\d.,]+)\s*€"), "EUR", 1.0),
    (re.compile(r"([\d.,]+)\s*£"), "GBP", GBP_TO_EUR),
]


def _parse_amount(raw: str) -> Optional[float]:
    s = raw.strip().replace(",", "")
    try:
        v = float(s)
        return v if v > 0 else None
    except ValueError:
        return None


def normalize_linkedin_url(url: str) -> str:
    u = url.strip().rstrip("/")
    if not u.lower().startswith("http"):
        u = f"https://{u.lstrip('/')}"
    return u


def extract_linkedin_from_text(text: str) -> Optional[str]:
    """Prefer personal /in/ profiles; fall back to company page."""
    if not text:
        return None
    person: Optional[str] = None
    company: Optional[str] = None
    for m in _LINKEDIN_URL_RE.finditer(text[:DISCOVERY_MAX_CHARS]):
        url = normalize_linkedin_url(m.group(0))
        if "/in/" in url.lower():
            person = person or url
        elif "/company/" in url.lower():
            company = company or url
    if not person and not company:
        for m in _LINKEDIN_BARE_RE.finditer(text[:DISCOVERY_MAX_CHARS]):
            kind, slug = m.group(1).lower(), m.group(2)
            url = normalize_linkedin_url(f"https://www.linkedin.com/{kind}/{slug}")
            if kind == "in":
                person = person or url
            else:
                company = company or url
    return person or company


def extract_email_from_text(text: str) -> Optional[str]:
    if not text:
        return None
    emails = _EMAIL_RE.findall(text)
    valid = [
        e
        for e in emails
        if not any(x in e.lower() for x in _EMAIL_BLOCK)
        and not e.lower().endswith((".png", ".jpg", ".gif"))
    ]
    preferred = [e for e in valid if any(p in e.lower() for p in _EMAIL_PREFERRED)]
    if preferred:
        return preferred[0]
    return valid[0] if valid else None


def extract_hq_city_from_text(text: str) -> Optional[str]:
    if not text:
        return None
    for pat in _HQ_PATTERNS:
        m = pat.search(text)
        if m:
            city = m.group(1).strip()
            if 2 <= len(city) <= 40:
                return city
    return None


def extract_store_hints_from_text(text: str) -> Dict[str, Any]:
    """Explicit store count or addresses only — conservative."""
    out: Dict[str, Any] = {
        "site_store_addresses": [],
        "site_store_count": None,
        "site_store_confidence": "unknown",
    }
    if not text:
        return out
    m = _STORE_COUNT_RE.search(text)
    if m:
        count = int(m.group(1))
        if 1 <= count <= 500:
            out["site_store_count"] = count
            out["site_store_confidence"] = "verified"
    return out


def extract_price_hints_from_text(text: str) -> Dict[str, Any]:
    """Find suit-related EUR amounts when explicitly priced in discovery text."""
    out: Dict[str, Any] = {
        "avg_suit_price_eur": None,
        "price_range_min_eur": None,
        "price_range_max_eur": None,
    }
    if not text:
        return out

    window = text[:DISCOVERY_MAX_CHARS].lower()
    if "suit" not in window and "fato" not in window and "jacket" not in window:
        return out

    amounts: List[float] = []
    for pattern, _cur, mult in _PRICE_PATTERNS:
        for m in pattern.finditer(text[:DISCOVERY_MAX_CHARS]):
            amt = _parse_amount(m.group(1))
            if amt and 200 <= amt * mult <= 5000:
                amounts.append(round(amt * mult, 2))

    if not amounts:
        return out

    amounts = sorted(set(amounts))
    out["price_range_min_eur"] = amounts[0]
    out["price_range_max_eur"] = amounts[-1]
    out["avg_suit_price_eur"] = round(sum(amounts) / len(amounts), 2)
    return out


def prefill_from_discovery(brand: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse discovery content (≤10k chars). Returns fields to merge into brand;
    HQ only when explicit phrase matched (confidence verified).
    """
    text = (brand.get("text") or brand.get("highlights") or "")[:DISCOVERY_MAX_CHARS]
    result: Dict[str, Any] = {}

    email = extract_email_from_text(text)
    if email:
        result["contact_email"] = email

    linkedin = extract_linkedin_from_text(text)
    if linkedin:
        result["contact_linkedin"] = linkedin

    price = extract_price_hints_from_text(text)
    result.update({k: v for k, v in price.items() if v is not None})

    hq_city = extract_hq_city_from_text(text)
    if hq_city:
        result["headquarters_city"] = hq_city
        result["headquarters_confidence"] = "verified"

    stores = extract_store_hints_from_text(text)
    if stores.get("site_store_confidence") == "verified":
        result.update(stores)

    return result


def apply_prefill(brand: Dict[str, Any], prefill: Dict[str, Any]) -> None:
    """Merge prefill into brand without overwriting stronger existing values."""
    for key, value in prefill.items():
        if value is None:
            continue
        if key == "headquarters_confidence":
            if brand.get("headquarters_confidence") == "verified":
                continue
        elif brand.get(key) not in (None, "", [], 0):
            continue
        brand[key] = value
