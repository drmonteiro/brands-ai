"""
Turn LLM price findings into prices we can stand behind.

The LLM only reports what it read. Code decides what counts: the quote must really
be in the brand's own text, it must contain the amount, and the product must be a
whole suit. Anything else leaves the price unconfirmed rather than guessed.
"""

import re
import statistics
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from services.currency import to_eur

MAX_STORED_EVIDENCE = 5
# Beyond these, a number is a parsing mistake and not a suit price.
PLAUSIBLE_MIN_EUR = 50
PLAUSIBLE_MAX_EUR = 20000

_SUIT_TERMS = re.compile(
    r"\b(suits?|two[- ]piece|three[- ]piece|fatos?|trajes?|ternos?|abito|abiti|"
    r"\w*anzug|\w*anzüge|\w*anzuege|costumes?|kostym|kostymer|kostuum|pak|garnitur)\b",
    re.IGNORECASE,
)
_NOT_A_SUIT = re.compile(
    r"swim\s?suit|track\s?suit|jump\s?suit|play\s?suit|suit\s?case|"
    r"\bsuit\s+(bag|carrier|cover|hanger|jacket|trousers?|pants?|waistcoat|vest|hire|rental|alterations?|press|care|fabric)\b|"
    r"\b(hire|rental|alterations?|fabric|cloth|accessor)",
    re.IGNORECASE,
)


def parse_amount(raw: Any) -> Optional[float]:
    """Read '1,295', '1.295', '1.295,00', '1,295.00', "1'295" or '495,00' as a number."""
    if isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        return float(raw) if raw > 0 else None
    text = re.sub(r"[\s'  ]", "", str(raw or ""))
    text = re.sub(r"[^\d.,]", "", text)
    if not re.search(r"\d", text):
        return None
    if "." in text and "," in text:
        decimal = "." if text.rfind(".") > text.rfind(",") else ","
        thousands = "," if decimal == "." else "."
        text = text.replace(thousands, "").replace(decimal, ".")
    else:
        sep = "." if "." in text else "," if "," in text else None
        if sep:
            parts = text.split(sep)
            # A single group of exactly three digits after the separator is thousands.
            if len(parts) > 2 or len(parts[-1]) == 3:
                text = "".join(parts)
            else:
                text = ".".join(parts)
    try:
        value = float(text)
    except ValueError:
        return None
    return value if value > 0 else None


def normalize_text(text: str) -> str:
    """Compare quotes ignoring case, spacing and punctuation differences such as markdown."""
    return " ".join(re.sub(r"[^\w€£$]+", " ", (text or "").lower()).split())


def quote_in_text(quote: str, source_text: str) -> bool:
    """True if a meaningful quote appears in the source. `source_text` must be normalized."""
    normalized = normalize_text(quote)
    return len(normalized) >= 8 and normalized in source_text


def _domain(url: str) -> str:
    host = urlparse(url if "//" in (url or "") else f"//{url}").netloc.lower().split(":")[0]
    return host[4:] if host.startswith("www.") else host


def same_site(url: str, website_url: str) -> bool:
    a, b = _domain(url), _domain(website_url)
    return bool(a and b) and (a == b or a.endswith(f".{b}") or b.endswith(f".{a}"))


def is_whole_suit(product: str) -> bool:
    text = product or ""
    return bool(_SUIT_TERMS.search(text)) and not _NOT_A_SUIT.search(text)


def _amount_in_quote(amount: float, quote: str) -> bool:
    found = (parse_amount(m) for m in re.findall(r"\d[\d.,'\s ]*\d|\d", quote or ""))
    return any(v is not None and abs(v - amount) < 1 for v in found)


def confirm_suit_prices(
    findings: Any,
    website_url: str,
    source_text: str,
) -> Dict[str, Any]:
    """Returns the brand's price fields. Without one valid finding, the price is unconfirmed."""
    normalized_source = normalize_text(source_text)
    confirmed: List[Dict[str, Any]] = []

    for item in findings if isinstance(findings, list) else []:
        if not isinstance(item, dict):
            continue
        amount = parse_amount(item.get("amount"))
        quote = str(item.get("quote") or "")
        product = str(item.get("product") or "")
        source_url = str(item.get("source_url") or "")
        if amount is None or not is_whole_suit(product):
            continue
        if not same_site(source_url, website_url):
            continue
        if not quote_in_text(quote, normalized_source) or not _amount_in_quote(amount, quote):
            continue
        amount_eur = to_eur(amount, str(item.get("currency") or ""))
        if amount_eur is None or not PLAUSIBLE_MIN_EUR <= amount_eur <= PLAUSIBLE_MAX_EUR:
            continue
        confirmed.append({
            "amount": amount,
            "currency": str(item["currency"]).upper(),
            "amount_eur": round(amount_eur, 2),
            "product": product[:120],
            "quote": quote[:300],
            "source_url": source_url,
        })

    if not confirmed:
        return {
            "price_status": "unconfirmed",
            "avg_suit_price_eur": None,
            "price_range_min_eur": None,
            "price_range_max_eur": None,
            "price_source_url": None,
            "price_evidence": [],
        }

    amounts = sorted(c["amount_eur"] for c in confirmed)
    return {
        "price_status": "confirmed",
        "avg_suit_price_eur": round(statistics.median(amounts), 2),
        "price_range_min_eur": amounts[0],
        "price_range_max_eur": amounts[-1],
        "price_source_url": min(confirmed, key=lambda c: c["amount_eur"])["source_url"],
        "price_evidence": confirmed[:MAX_STORED_EVIDENCE],
    }
