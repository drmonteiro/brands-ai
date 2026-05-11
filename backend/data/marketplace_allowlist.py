"""
Marketplace Own-Brand Allowlist for Confeções Lança Prospector

Some marketplace domains host independent own-brand labels that
are legitimate manufacturing partners (e.g., Mr P. on Mr Porter).
This allowlist prevents them from being excluded by the domain-level
marketplace filter in Phase 0.

Format: list of dicts with:
  - brand: Display name of the own-brand label
  - parent_marketplace: Parent marketplace name
  - domain_pattern: Substring to match against the URL domain
  - notes: Why this is allowlisted
"""
from typing import Dict, List, Optional


MARKETPLACE_ALLOWLIST: List[Dict[str, str]] = [
    {
        "brand": "Mr P.",
        "parent_marketplace": "MR PORTER",
        "domain_pattern": "mrporter.com",
        "notes": "MR PORTER's own-brand menswear label with tailored suits and jackets in the €500-€1000 range",
    },
    {
        "brand": "COS",
        "parent_marketplace": "H&M Group",
        "domain_pattern": "cos.com",
        "notes": "COS operates independently with own-brand premium minimalist collections, though parent is H&M Group",
    },
    {
        "brand": "Arket",
        "parent_marketplace": "H&M Group",
        "domain_pattern": "arket.com",
        "notes": "Arket is an independent premium brand within H&M Group",
    },
]

# Pre-computed set of allowlisted domain patterns for fast lookup
_ALLOWLIST_DOMAINS = {entry["domain_pattern"] for entry in MARKETPLACE_ALLOWLIST}


def is_allowlisted_marketplace(url: str) -> bool:
    """Check if a URL belongs to an allowlisted marketplace own-brand."""
    url_lower = url.lower()
    return any(pattern in url_lower for pattern in _ALLOWLIST_DOMAINS)


def get_allowlist_entry(url: str) -> Optional[Dict[str, str]]:
    """Get the allowlist entry for a URL, or None if not allowlisted."""
    url_lower = url.lower()
    for entry in MARKETPLACE_ALLOWLIST:
        if entry["domain_pattern"] in url_lower:
            return entry
    return None
