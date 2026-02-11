"""
Premium Retail Locations Database

This module contains a curated list of premium/luxury shopping streets
for major cities worldwide, used to detect if a brand has stores in
high-end retail locations.

Data sourced from:
- RetailWeek Top Shopping Streets
- Cushman & Wakefield Main Streets Across the World
- Industry knowledge of luxury retail districts
"""

from typing import Dict, List, Tuple, Optional

# ============================================================================
# PREMIUM STREETS DATABASE
# ============================================================================
# 
# Format: city_key -> list of (street_name, tier)
# Tiers:
#   1 = Ultra-premium (Bond Street, Fifth Avenue)
#   2 = Premium (Regent Street, Madison Avenue)
#   3 = High-end (Covent Garden, Soho)
#

PREMIUM_STREETS: Dict[str, List[Tuple[str, int]]] = {
    # ========== UNITED KINGDOM ==========
    "london": [
        # Tier 1 - Ultra Premium
        ("new bond street", 1),
        ("old bond street", 1),
        ("savile row", 1),
        ("mount street", 1),
        # Tier 2 - Premium
        ("regent street", 2),
        ("jermyn street", 2),
        ("sloane street", 2),
        ("knightsbridge", 2),
        ("brompton road", 2),
        ("burlington arcade", 2),
        # Tier 3 - High-end
        ("covent garden", 3),
        ("kings road", 3),
        ("marylebone high street", 3),
        ("south molton street", 3),
    ],
    "manchester": [
        ("king street", 2),
        ("spinningfields", 2),
        ("st ann's square", 2),
    ],
    "edinburgh": [
        ("george street", 2),
        ("multrees walk", 2),
        ("princes street", 3),
    ],
    
    # ========== FRANCE ==========
    "paris": [
        # Tier 1 - Ultra Premium
        ("avenue montaigne", 1),
        ("rue du faubourg saint-honoré", 1),
        ("place vendôme", 1),
        ("rue saint-honoré", 1),
        # Tier 2 - Premium
        ("champs-élysées", 2),
        ("boulevard haussmann", 2),
        ("rue de la paix", 2),
        # Tier 3 - High-end
        ("le marais", 3),
        ("saint-germain-des-prés", 3),
    ],
    
    # ========== ITALY ==========
    "milan": [
        ("via montenapoleone", 1),
        ("via della spiga", 1),
        ("galleria vittorio emanuele", 1),
        ("corso venezia", 2),
        ("via sant'andrea", 2),
    ],
    "rome": [
        ("via condotti", 1),
        ("via del corso", 2),
        ("via borgognona", 2),
    ],
    "florence": [
        ("via de' tornabuoni", 1),
        ("via della vigna nuova", 2),
    ],
    
    # ========== SPAIN ==========
    "madrid": [
        ("calle serrano", 1),
        ("calle josé ortega y gasset", 1),
        ("barrio de salamanca", 2),
        ("gran vía", 3),
    ],
    "barcelona": [
        ("passeig de gràcia", 1),
        ("la rambla", 3),
        ("diagonal", 3),
    ],
    
    # ========== PORTUGAL ==========
    "lisbon": [
        ("avenida da liberdade", 1),
        ("chiado", 2),
        ("príncipe real", 3),
    ],
    "porto": [
        ("avenida dos aliados", 2),
        ("rua santa catarina", 3),
    ],
    
    # ========== GERMANY ==========
    "berlin": [
        ("kurfürstendamm", 2),
        ("friedrichstraße", 2),
    ],
    "munich": [
        ("maximilianstraße", 1),
        ("theatinerstraße", 2),
    ],
    "düsseldorf": [
        ("königsallee", 1),
    ],
    
    # ========== UNITED STATES ==========
    "new york": [
        ("fifth avenue", 1),
        ("madison avenue", 1),
        ("57th street", 1),
        ("soho", 2),
        ("bleecker street", 3),
        ("tribeca", 3),
    ],
    "los angeles": [
        ("rodeo drive", 1),
        ("beverly hills", 2),
        ("melrose avenue", 3),
    ],
    "chicago": [
        ("magnificent mile", 1),
        ("oak street", 2),
    ],
    "miami": [
        ("design district", 2),
        ("bal harbour", 2),
    ],
    "boston": [
        ("newbury street", 2),
        ("back bay", 3),
    ],
    "san francisco": [
        ("union square", 2),
    ],
    
    # ========== AUSTRIA ==========
    "vienna": [
        ("kohlmarkt", 1),
        ("graben", 2),
        ("kärntner straße", 2),
    ],
    
    # ========== BELGIUM ==========
    "brussels": [
        ("avenue louise", 2),
        ("boulevard de waterloo", 2),
    ],
    "antwerp": [
        ("meir", 2),
        ("schuttershofstraat", 2),
    ],
    
    # ========== CZECH REPUBLIC ==========
    "prague": [
        ("pařížská", 1),
        ("na příkopě", 2),
    ],
    
    # ========== SWITZERLAND ==========
    "zurich": [
        ("bahnhofstrasse", 1),
    ],
    "geneva": [
        ("rue du rhône", 1),
    ],
    
    # ========== NETHERLANDS ==========
    "amsterdam": [
        ("p.c. hooftstraat", 1),
        ("van baerlestraat", 2),
    ],
    
    # ========== SOUTH AMERICA ==========
    "são paulo": [
        ("rua oscar freire", 1),
        ("jardins", 2),
    ],
    "buenos aires": [
        ("avenida alvear", 1),
        ("recoleta", 2),
    ],
    "bogota": [
        ("zona rosa", 2),
        ("usaquén", 3),
    ],
    "lima": [
        ("miraflores", 2),
        ("san isidro", 2),
    ],
    
    # ========== AFRICA ==========
    "luanda": [
        ("marginal", 2),
        ("talatona", 3),
    ],
}


# ============================================================================
# DETECTION FUNCTIONS
# ============================================================================

def normalize_text(text: str) -> str:
    """Normalize text for matching (lowercase, handle accents loosely)."""
    return text.lower().strip()


def detect_premium_location(content: str, city: str) -> Tuple[Optional[str], Optional[int]]:
    """
    Detect if content mentions a premium retail location.
    
    Args:
        content: Website content or address text
        city: The city to check for
        
    Returns:
        Tuple of (street_name, tier) if found, or (None, None)
    """
    city_key = normalize_text(city)
    content_lower = normalize_text(content)
    
    # Check if we have data for this city
    if city_key not in PREMIUM_STREETS:
        return None, None
    
    # Search for premium streets in content
    for street, tier in PREMIUM_STREETS[city_key]:
        if street in content_lower:
            return street, tier
    
    return None, None


def calculate_location_score(street_name: Optional[str], tier: Optional[int]) -> int:
    """
    Calculate location score based on detected premium street.
    
    Returns:
        0-10 points based on tier:
        - Tier 1 (Ultra-premium): 10 pts
        - Tier 2 (Premium): 7 pts
        - Tier 3 (High-end): 4 pts
        - Unknown/Not found: 0 pts
    """
    if tier is None:
        return 0
    
    tier_scores = {
        1: 10,  # Ultra-premium
        2: 7,   # Premium
        3: 4,   # High-end
    }
    return tier_scores.get(tier, 0)


def get_supported_cities() -> List[str]:
    """Get list of cities with premium street data."""
    return list(PREMIUM_STREETS.keys())


def has_city_data(city: str) -> bool:
    """Check if we have premium street data for a city."""
    return normalize_text(city) in PREMIUM_STREETS


# ============================================================================
# CLI TEST
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("📍 Premium Locations Database")
    print("=" * 60)
    print(f"\nSupported cities: {len(PREMIUM_STREETS)}")
    print(f"Total streets: {sum(len(streets) for streets in PREMIUM_STREETS.values())}")
    
    # Test detection
    print("\n🔍 Testing detection:")
    
    test_cases = [
        ("Visit our flagship on Bond Street, London", "london"),
        ("Located in Fifth Avenue, New York", "new york"),
        ("Find us at Avenida da Liberdade 123, Lisbon", "lisbon"),
        ("Shop in our downtown location", "london"),  # Should not find
    ]
    
    for content, city in test_cases:
        street, tier = detect_premium_location(content, city)
        score = calculate_location_score(street, tier)
        if street:
            print(f"  ✅ Found '{street}' (Tier {tier}) in {city} → {score} pts")
        else:
            print(f"  ❌ No premium location found in: '{content[:40]}...'")
