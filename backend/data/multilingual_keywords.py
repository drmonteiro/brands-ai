"""
Multi-Language Keyword Scoring System for Confeções Lança

Supports: English, Italian, French, German, Spanish, Portuguese
Each keyword has a score weight and the languages it applies to.
"*" means universal (brand names, technical terms that cross languages).

Scoring:
  +3 = Strong positive signal (bespoke, full canvas, premium fabric brands)
  +2 = Good positive signal (premium, luxury, tailoring)
  +1 = Mild positive signal (curated, independent, heritage)
  -3 = Strong negative (fast fashion, discount, outlet)
  -5 = Definitive exclusion (known fast-fashion chains by name)
"""

from typing import Dict, List, Tuple


# ============================================================================
# QUALITY KEYWORDS — Positive signals (+1 to +3)
# ============================================================================

QUALITY_KEYWORDS: Dict[str, Tuple[int, List[str]]] = {
    # === SCORE +3: Strong quality signals ===
    
    # Construction & Craftsmanship (English)
    "full canvas": (3, ["en"]),
    "full-canvas": (3, ["en"]),
    "hand-stitched": (3, ["en"]),
    "hand stitched": (3, ["en"]),
    "bespoke": (3, ["en"]),
    "working buttonholes": (3, ["en"]),
    "surgeon's cuffs": (3, ["en"]),
    "pick stitching": (3, ["en"]),
    "hand finished": (3, ["en"]),
    "hand-finished": (3, ["en"]),
    "handmade": (3, ["en"]),
    "trunk show": (3, ["en"]),
    
    # Construction (Italian)
    "interamente costruito": (3, ["it"]),      # Full canvas
    "cucito a mano": (3, ["it"]),              # Hand-stitched
    "su misura": (3, ["it"]),                  # Made-to-measure
    "sartoria": (3, ["it"]),                   # Tailoring house
    "sarto": (3, ["it"]),                      # Tailor
    "sartoriale": (3, ["it"]),                 # Sartorial
    "abito su misura": (3, ["it"]),            # Made-to-measure suit
    
    # Construction (French)
    "sur mesure": (3, ["fr"]),                 # Made-to-measure
    "grande mesure": (3, ["fr"]),              # Full bespoke
    "demi-mesure": (3, ["fr"]),                # Semi-bespoke
    "toile intégrale": (3, ["fr"]),            # Full canvas
    "tailleur": (3, ["fr"]),                   # Tailor
    "cousu main": (3, ["fr"]),                 # Hand-sewn
    "atelier de couture": (3, ["fr"]),         # Tailoring atelier
    "maison de couture": (3, ["fr"]),          # Fashion house
    
    # Construction (German)
    "maßanzug": (3, ["de"]),                   # Made-to-measure suit
    "nach maß": (3, ["de"]),                   # Made-to-measure
    "maßkonfektion": (3, ["de"]),              # Made-to-measure tailoring
    "maßschneiderei": (3, ["de"]),             # Bespoke tailoring
    "handgenäht": (3, ["de"]),                 # Hand-sewn
    "schneidermeister": (3, ["de"]),           # Master tailor
    "maßschneider": (3, ["de"]),               # Bespoke tailor
    
    # Construction (Spanish)
    "a medida": (3, ["es", "pt"]),             # Made-to-measure
    "hecho a medida": (3, ["es"]),             # Made-to-measure
    "sastrería": (3, ["es"]),                  # Tailoring
    "sastre": (3, ["es"]),                     # Tailor
    "cosido a mano": (3, ["es"]),              # Hand-sewn
    
    # Construction (Portuguese)
    "feito à medida": (3, ["pt"]),             # Made-to-measure
    "alfaiataria": (3, ["pt"]),                # Tailoring
    "alfaiate": (3, ["pt"]),                   # Tailor
    "costura a mão": (3, ["pt"]),              # Hand-sewn
    
    # Premium Fabric Brands (Universal — these brands signal premium everywhere)
    "loro piana": (3, ["*"]),
    "scabal": (3, ["*"]),
    "dormeuil": (3, ["*"]),
    "holland & sherry": (3, ["*"]),
    "holland and sherry": (3, ["*"]),
    "vitale barberis": (3, ["*"]),
    "vitale barberis canonico": (3, ["*"]),
    "cerruti": (3, ["*"]),
    "zegna cloth": (3, ["*"]),
    "ermenegildo zegna": (2, ["*"]),
    "drago": (2, ["*"]),
    "reda": (2, ["*"]),
    "guabello": (2, ["*"]),
    "trabaldo togna": (3, ["*"]),
    "carlo barbera": (3, ["*"]),
    "caccioppoli": (3, ["*"]),
    "huddersfield cloth": (3, ["*"]),
    "fox brothers": (3, ["*"]),
    "moon tweed": (2, ["*"]),
    "harris tweed": (2, ["*"]),
    "abraham moon": (2, ["*"]),
    "super 110": (2, ["*"]),
    "super 120": (2, ["*"]),
    "super 130": (3, ["*"]),
    "super 150": (3, ["*"]),
    "super 160": (3, ["*"]),
    "super 180": (3, ["*"]),
    
    # === SCORE +2: Good signals ===
    
    # English
    "made to measure": (2, ["en"]),
    "made-to-measure": (2, ["en"]),
    "custom tailoring": (2, ["en"]),
    "custom suit": (2, ["en"]),
    "sartorial": (2, ["en"]),
    "canvassed": (2, ["en"]),
    "half canvas": (2, ["en"]),
    "half-canvas": (2, ["en"]),
    "atelier": (2, ["*"]),                     # Universal
    "savile row": (2, ["*"]),
    "tailored": (2, ["en"]),
    
    # Italian
    "abiti da uomo": (2, ["it"]),              # Men's suits
    "abiti da cerimonia": (2, ["it"]),          # Ceremony suits
    "lana vergine": (2, ["it"]),               # Virgin wool
    "pura lana": (2, ["it"]),                  # Pure wool
    
    # French
    "costume homme": (2, ["fr"]),              # Men's suit
    "costume sur mesure": (2, ["fr"]),         # Made-to-measure suit
    "laine vierge": (2, ["fr"]),              # Virgin wool
    "pure laine": (2, ["fr"]),                # Pure wool
    
    # German
    "herrenanzug": (2, ["de"]),                # Men's suit
    "maßgeschneidert": (2, ["de"]),            # Custom-tailored
    "reine wolle": (2, ["de"]),                # Pure wool
    "schurwolle": (2, ["de"]),                 # Virgin wool
    
    # Spanish
    "traje a medida": (2, ["es"]),             # Made-to-measure suit
    "traje de novio": (2, ["es"]),             # Groom's suit
    "lana virgen": (2, ["es"]),                # Virgin wool
    "pura lana": (2, ["es"]),                  # Pure wool (also IT)
    
    # Portuguese
    "fato à medida": (2, ["pt"]),              # Made-to-measure suit
    "fato de noivo": (2, ["pt"]),              # Groom's suit
    "lã virgem": (2, ["pt"]),                  # Virgin wool
    "pura lã": (2, ["pt"]),                    # Pure wool
    
    # === SCORE +1: Mild positive signals ===
    
    # English
    "premium": (1, ["en"]),
    "luxury": (1, ["en"]),
    "high-end": (1, ["en"]),
    "high end": (1, ["en"]),
    "independent boutique": (1, ["en"]),
    "menswear specialist": (1, ["en"]),
    "heritage tailoring": (1, ["en"]),
    "curated": (1, ["en"]),
    "exclusive": (1, ["*"]),
    "100% wool": (2, ["en"]),
    "pure new wool": (2, ["en"]),
    
    # Italian
    "boutique indipendente": (1, ["it"]),
    "lusso": (1, ["it"]),
    "alta gamma": (1, ["it"]),
    "100% lana": (2, ["it"]),
    
    # French
    "boutique indépendante": (1, ["fr"]),
    "luxe": (1, ["fr"]),
    "haut de gamme": (1, ["fr"]),
    "100% laine": (2, ["fr"]),
    
    # German
    "luxus": (1, ["de"]),
    "hochwertig": (1, ["de"]),
    "exklusiv": (1, ["de"]),
    "100% wolle": (2, ["de"]),
    
    # Spanish
    "boutique independiente": (1, ["es"]),
    "lujo": (1, ["es"]),
    "alta gama": (1, ["es"]),
    "100% lana": (2, ["es"]),
    
    # Portuguese
    "boutique independente": (1, ["pt"]),
    "luxo": (1, ["pt"]),
    "alta gama": (1, ["pt"]),
    "100% lã": (2, ["pt"]),
}


# ============================================================================
# EXCLUSION KEYWORDS — Negative signals (-3 to -5)
# ============================================================================

EXCLUSION_KEYWORDS: Dict[str, Tuple[int, List[str]]] = {
    # === SCORE -5: Definitive exclusion (brand names) ===
    "h&m": (-5, ["*"]),
    "zara": (-5, ["*"]),
    "mango": (-5, ["*"]),
    "primark": (-5, ["*"]),
    "shein": (-5, ["*"]),
    "uniqlo": (-5, ["*"]),
    "walmart": (-5, ["*"]),
    "target store": (-5, ["en"]),
    "amazon fashion": (-5, ["*"]),
    "asos": (-5, ["*"]),
    "boohoo": (-5, ["*"]),
    
    # === SCORE -3: Strong negative signals ===
    # English
    "fast fashion": (-3, ["en"]),
    "discount": (-3, ["en"]),
    "outlet": (-3, ["*"]),
    "clearance": (-3, ["en"]),
    "ebay": (-3, ["*"]),
    "rental only": (-3, ["en"]),
    "hire only": (-3, ["en"]),
    "costume rental": (-3, ["en"]),
    "halloween": (-3, ["*"]),
    "fancy dress": (-3, ["en"]),
    "thrift": (-3, ["en"]),
    "second hand suit": (-3, ["en"]),
    "used clothing": (-3, ["en"]),
    
    # Italian
    "moda veloce": (-3, ["it"]),
    "saldi": (-3, ["it"]),                     # Sales/clearance
    "noleggio": (-3, ["it"]),                  # Rental
    
    # French
    "mode rapide": (-3, ["fr"]),
    "soldes": (-3, ["fr"]),                    # Sales
    "location de costumes": (-3, ["fr"]),       # Costume rental
    "déstockage": (-3, ["fr"]),                # Clearance
    
    # German
    "schnäppchen": (-3, ["de"]),               # Bargain
    "gebrauchte kleidung": (-3, ["de"]),        # Used clothing
    "verleih": (-3, ["de"]),                   # Rental
    
    # Spanish
    "moda rápida": (-3, ["es"]),
    "descuento": (-3, ["es"]),
    "alquiler": (-3, ["es"]),                  # Rental
    "rebajas": (-3, ["es"]),                   # Sales
    
    # Portuguese
    "moda rápida": (-3, ["pt"]),
    "desconto": (-3, ["pt"]),
    "aluguer": (-3, ["pt"]),                   # Rental
    "saldos": (-3, ["pt"]),                    # Sales
}


# ============================================================================
# KNOWN CHAINS — Instant exclusion before scraping
# ============================================================================

KNOWN_CHAIN_DOMAINS = {
    # Fast Fashion
    "hm.com", "zara.com", "mango.com", "primark.com", "uniqlo.com",
    "shein.com", "asos.com", "boohoo.com", "cos.com",
    
    # Mid-range chains (too big for Lança partnership)
    "suitsupply.com", "boggi.com", "boggi.it", "mossbros.com", "charlestyrwhitt.com",
    "tmlewin.com", "tmlewin.co.uk", "charlesyrwhitt.co.uk",
    "hugoboss.com", "boss.com", "tedbaker.com", "reiss.com",
    "massimodutti.com", "jcrew.com", "brooksbrothers.com",
    "ralphlauren.com", "josephabboud.com", "menswearhouse.com",
    "josbanka.com", "indochino.com",
    
    # Department Stores
    "selfridges.com", "harrods.com", "liberty.co.uk",
    "johnlewis.com", "nordstrom.com", "saksfifthavenue.com",
    "neimanmarcus.com", "bloomingdales.com", "barneys.com",
    "elcorteingles.es", "elcorteingles.pt",
    "larinascente.it", "galerieslafayette.com",
    "harveynichols.com", "theoutnet.com", "mrporter.com",
    
    # E-commerce Giants  
    "amazon.com", "ebay.com", "walmart.com", "target.com",
    "alibaba.com", "aliexpress.com",
    
    # Review/Listing sites (not actual retailers)
    "yelp.com", "yellowpages.com", "tripadvisor.com",
    "trustpilot.com", "glassdoor.com", "indeed.com",
    "facebook.com", "instagram.com", "twitter.com",
    "linkedin.com", "pinterest.com", "tiktok.com",
    "reddit.com", "quora.com",
    "wikipedia.org", "wikidata.org",
}

KNOWN_CHAIN_NAMES = {
    # Luxury conglomerates (too big)
    "lvmh", "kering", "richemont", "tapestry",
    
    # Known large brands
    "suitsupply", "suit supply", "moss bros", "moss brothers",
    "charles tyrwhitt", "tm lewin", "t.m. lewin",
    "hugo boss", "ted baker", "reiss", "paul smith",
    "massimo dutti", "cos", "uniqlo",
    "ralph lauren", "brooks brothers", "j.crew", "j crew",
    "men's wearhouse", "jos a bank", "jos. a. bank",
    "indochino", "bonobos",
    
    # Fast fashion
    "h&m", "zara", "mango", "primark", "shein",
    "asos", "boohoo", "plt", "prettylittlething",
}


# ============================================================================
# SCORING FUNCTIONS
# ============================================================================

def calculate_keyword_score(content: str, url: str = "", detected_language: str = None, verbose: bool = False) -> int:
    """
    Calculate the quality score for content using multi-language keyword matching.
    
    Args:
        content: The scraped website content (first ~8000 chars)
        url: The URL of the website
        detected_language: ISO 639-1 language code (e.g., "en", "it", "fr")
        verbose: If True, also return matched keywords grouped by language.
    
    Returns:
        Integer score (or tuple of (score, details_dict) if verbose=True).
        Score >= 2 is considered worth investigating.
    """
    text = (content or "").lower()[:8000]
    url_text = (url or "").lower()
    combined = text + " " + url_text
    
    score = 0
    matched_keywords = []
    per_lang_hits = {}  # lang -> list of (keyword, weight)
    
    for keyword, (weight, languages) in QUALITY_KEYWORDS.items():
        if detected_language and "*" not in languages and detected_language not in languages:
            continue
        
        if keyword in combined:
            score += weight
            matched_keywords.append((keyword, weight))
            for lang in languages:
                per_lang_hits.setdefault(lang, []).append((keyword, weight))
    
    for keyword, (weight, languages) in EXCLUSION_KEYWORDS.items():
        if detected_language and "*" not in languages and detected_language not in languages:
            continue
        
        if keyword in combined:
            score += weight
            matched_keywords.append((keyword, weight))
            for lang in languages:
                per_lang_hits.setdefault(lang, []).append((keyword, weight))
    
    if verbose:
        details = {
            "total_score": score,
            "detected_language": detected_language,
            "matched_count": len(matched_keywords),
            "per_language_hits": {lang: len(hits) for lang, hits in per_lang_hits.items()},
            "matched_keywords": matched_keywords,
        }
        return score, details
    
    return score


def is_known_chain(url: str, name: str = "") -> bool:
    """
    Check if a URL or brand name matches a known chain/exclusion.
    Should be called BEFORE scraping to save API costs.
    
    Args:
        url: The candidate URL
        name: The brand name (if known)
    
    Returns:
        True if this is a known chain that should be excluded.
    """
    # Check domain
    url_lower = url.lower()
    for domain in KNOWN_CHAIN_DOMAINS:
        if domain in url_lower:
            return True
    
    # Check name
    if name:
        name_lower = name.lower().strip()
        for chain in KNOWN_CHAIN_NAMES:
            if chain in name_lower or name_lower in chain:
                return True
    
    return False
