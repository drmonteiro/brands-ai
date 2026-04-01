"""
Price Extraction Service V2
Extracts and averages SUIT prices from text content.

Key fixes over V1:
- Fixed European number format bug (1.299,00 € was parsed as 12.99€)
- Added context-aware price extraction (only prices near suit-related keywords)
- Added currency detection and conversion
- Added price confidence scoring
"""
import re
from typing import Dict, List, Tuple, Optional


# Currency conversion rates to EUR (approximate)
CURRENCY_TO_EUR = {
    "EUR": 1.0,
    "€": 1.0,
    "USD": 0.92,
    "$": 0.92,
    "GBP": 1.17,
    "£": 1.17,
    "CHF": 1.05,
    "SEK": 0.088,
    "DKK": 0.134,
    "NOK": 0.087,
    "CZK": 0.041,
    "PLN": 0.23,
    "JPY": 0.0062,
    "AUD": 0.60,
    "CAD": 0.68,
    "AED": 0.25,
    "COP": 0.00023,
    "PEN": 0.25,
    "BRL": 0.18,
}

# Keywords that indicate we're looking at suit/jacket/trouser-relevant prices
SUIT_CONTEXT_KEYWORDS = [
    # English — Suits
    "suit", "suits", "tuxedo", "dinner jacket", "morning coat",
    "two-piece", "three-piece", "two piece", "three piece",
    # English — Jackets / Blazers
    "blazer", "blazers", "jacket", "jackets", "sport coat", "sports coat",
    # English — Trousers
    "trouser", "trousers", "pant", "pants", "chino", "chinos",
    # English — Waistcoats
    "waistcoat", "waistcoats", "vest", "gilet",
    # Italian
    "abito", "abiti", "completo", "smoking", "giacca", "giacche",
    "pantalone", "pantaloni", "gilet",
    # French
    "costume", "costumes", "veste", "smoking", "complet",
    "pantalon", "pantalons", "gilet",
    # German
    "anzug", "anzüge", "sakko", "smoking",
    "hose", "hosen",
    # Spanish
    "traje", "trajes", "chaqueta", "esmoquin",
    "pantalón", "pantalones", "chaleco",
    # Portuguese
    "fato", "fatos", "blazer", "smoking",
    "calça", "calças", "colete",
]

# Keywords that indicate NON-suit products (to exclude their prices)
NON_SUIT_KEYWORDS = [
    "shirt", "tie", "belt", "shoe", "sock", "underwear", "cufflink",
    "camisa", "gravata", "cinto", "sapato", "meia",
    "chemise", "cravate", "ceinture", "chaussure",
    "hemd", "krawatte", "gürtel", "schuh",
    "camicia", "cravatta", "cintura", "scarpa",
]


def _parse_number(raw: str) -> Optional[float]:
    """
    Parse a number string handling both European and US formats correctly.
    
    US format:  1,299.00 → 1299.00
    EU format:  1.299,00 → 1299.00
    Compact:    1299     → 1299.00
    
    Key insight: If there's a separator followed by exactly 2 digits at the end,
    those 2 digits are decimals. Anything else is a thousands separator.
    """
    if not raw:
        return None
    
    raw = raw.strip()
    
    # Remove spaces/non-breaking spaces used as thousands separators
    raw = raw.replace('\u00a0', '').replace('\u202f', '').replace(' ', '')
    
    # Determine format by looking at the LAST separator
    has_comma = ',' in raw
    has_dot = '.' in raw
    
    if has_comma and has_dot:
        # Both separators present — determine which is the decimal
        last_comma = raw.rfind(',')
        last_dot = raw.rfind('.')
        
        if last_comma > last_dot:
            # Format: 1.299,00 → European (comma is decimal)
            raw = raw.replace('.', '')  # Remove thousands dots
            raw = raw.replace(',', '.')  # Convert decimal comma to dot
        else:
            # Format: 1,299.00 → US (dot is decimal)
            raw = raw.replace(',', '')  # Remove thousands commas
    elif has_comma:
        # Only commas — check if it's a decimal or thousands separator
        parts = raw.split(',')
        if len(parts) == 2 and len(parts[1]) == 2:
            # Likely decimal: 899,00 → 899.00
            raw = raw.replace(',', '.')
        elif len(parts) == 2 and len(parts[1]) == 3:
            # Likely thousands: 1,299 → 1299
            raw = raw.replace(',', '')
        else:
            # Multiple commas or ambiguous → treat as thousands
            raw = raw.replace(',', '')
    elif has_dot:
        # Only dots — check if it's a decimal or thousands separator
        parts = raw.split('.')
        if len(parts) == 2 and len(parts[1]) == 2:
            # Likely decimal: 899.00 → 899.00 (already correct)
            pass
        elif len(parts) == 2 and len(parts[1]) == 3:
            # Likely thousands: 1.299 → 1299
            raw = raw.replace('.', '')
        else:
            # Multiple dots → treat as thousands
            raw = raw.replace('.', '')
    
    try:
        return float(raw)
    except ValueError:
        return None


def _get_currency_from_match(prefix: str, suffix: str) -> str:
    """Identify currency from prefix/suffix symbols."""
    combined = (prefix + suffix).strip()
    if '€' in combined or 'EUR' in combined.upper():
        return "EUR"
    elif '£' in combined or 'GBP' in combined.upper():
        return "GBP"
    elif '$' in combined or 'USD' in combined.upper():
        return "USD"
    elif 'CHF' in combined.upper():
        return "CHF"
    elif 'SEK' in combined.upper() or 'kr' in combined:
        return "SEK"
    elif 'DKK' in combined.upper():
        return "DKK"
    elif 'NOK' in combined.upper():
        return "NOK"
    elif 'CZK' in combined.upper() or 'Kč' in combined:
        return "CZK"
    elif 'R$' in combined or 'BRL' in combined.upper():
        return "BRL"
    return "USD"  # Default fallback


def _is_near_suit_keyword(content: str, match_start: int, window: int = 300) -> bool:
    """Check if a price is near a suit-related keyword in the content."""
    start = max(0, match_start - window)
    end = min(len(content), match_start + window)
    context = content[start:end].lower()
    
    return any(kw in context for kw in SUIT_CONTEXT_KEYWORDS)


def _is_near_non_suit_keyword(content: str, match_start: int, window: int = 100) -> bool:
    """Check if a price is near a non-suit product keyword (closer window)."""
    start = max(0, match_start - window)
    end = min(len(content), match_start + window)
    context = content[start:end].lower()
    
    return any(kw in context for kw in NON_SUIT_KEYWORDS)


def extract_price_from_content(content: str) -> Dict[str, float]:
    """
    Extract and average suit prices from content with context awareness.
    
    Returns:
        {
            "avg_price": float (in EUR),
            "min_price": float (in EUR),
            "max_price": float (in EUR),
            "currency_detected": str,
            "price_count": int,
            "confidence": float (0.0-1.0)
        }
    """
    if not content:
        return {"avg_price": 0, "confidence": 0.0, "price_count": 0}
    
    # Master price pattern — captures:
    # Group 1: prefix currency (€, $, £)
    # Group 2: the number (with potential separators)
    # Group 3: suffix currency (€, $, £, EUR, GBP, USD, CHF, etc.)
    price_pattern = re.compile(
        r'([$€£])\s?'                                     # Prefix currency
        r'(\d{1,3}(?:[,.\s]\d{3})*(?:[.,]\d{2})?)'       # Number
        r'|'
        r'(\d{1,3}(?:[,.\s]\d{3})*(?:[.,]\d{2})?)'       # Number (no prefix)
        r'\s?([$€£]|EUR|GBP|USD|CHF|SEK|DKK|NOK|CZK|BRL|Kč|kr)',  # Suffix currency
        re.IGNORECASE
    )
    
    # Also match "from X" / "a partir de" / "à partir de" / "ab" / "da" patterns
    from_pattern = re.compile(
        r'(?:from|starting\s+at|a\s+partir\s+de|à\s+partir\s+de|ab|da|precio)\s*'
        r'[:=]?\s*'
        r'([$€£])?\s?(\d{1,3}(?:[,.\s]\d{3})*(?:[.,]\d{2})?)\s?([$€£]|EUR)?',
        re.IGNORECASE
    )
    
    all_prices_eur: List[float] = []
    suit_prices_eur: List[float] = []
    currencies_found: List[str] = []
    
    for match in price_pattern.finditer(content):
        prefix_currency = match.group(1) or ""
        number_with_prefix = match.group(2) or ""
        number_without_prefix = match.group(3) or ""
        suffix_currency = match.group(4) or ""
        
        number_str = number_with_prefix or number_without_prefix
        currency = _get_currency_from_match(prefix_currency, suffix_currency)
        
        val = _parse_number(number_str)
        if val is None:
            continue
        
        # Convert to EUR
        conversion_rate = CURRENCY_TO_EUR.get(currency, 0.92)
        val_eur = val * conversion_rate
        
        # Filter: reasonable suit price range (€150 — €8000 after conversion)
        if val_eur < 150 or val_eur > 8000:
            continue
        
        currencies_found.append(currency)
        all_prices_eur.append(val_eur)
        
        # Context check: is this price near a suit keyword?
        pos = match.start()
        if _is_near_suit_keyword(content, pos) and not _is_near_non_suit_keyword(content, pos):
            suit_prices_eur.append(val_eur)
    
    # Also process "from" patterns
    for match in from_pattern.finditer(content):
        prefix = match.group(1) or ""
        number_str = match.group(2) or ""
        suffix = match.group(3) or ""
        
        currency = _get_currency_from_match(prefix, suffix)
        val = _parse_number(number_str)
        if val is None:
            continue
        
        val_eur = val * CURRENCY_TO_EUR.get(currency, 0.92)
        if 150 < val_eur < 8000:
            currencies_found.append(currency)
            pos = match.start()
            if _is_near_suit_keyword(content, pos):
                suit_prices_eur.append(val_eur)
            all_prices_eur.append(val_eur)
    
    # Prioritize suit-context prices; fall back to all prices
    prices_to_use = suit_prices_eur if suit_prices_eur else all_prices_eur
    
    if not prices_to_use:
        return {"avg_price": 0, "confidence": 0.0, "price_count": 0}
    
    # Calculate confidence
    confidence = 0.0
    if suit_prices_eur:
        confidence = min(0.9, 0.5 + len(suit_prices_eur) * 0.1)
    elif all_prices_eur:
        confidence = min(0.5, 0.2 + len(all_prices_eur) * 0.05)
    
    # Determine dominant currency
    if currencies_found:
        dominant_currency = max(set(currencies_found), key=currencies_found.count)
    else:
        dominant_currency = "unknown"
    
    avg_price = sum(prices_to_use) / len(prices_to_use)
    
    return {
        "avg_price": round(avg_price, 2),
        "min_price": round(min(prices_to_use), 2),
        "max_price": round(max(prices_to_use), 2),
        "currency_detected": dominant_currency,
        "price_count": len(prices_to_use),
        "confidence": round(confidence, 2),
    }
