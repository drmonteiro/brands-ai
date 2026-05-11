"""
Contact Finder Service — Cascading approach to find C-level contacts.

Strategy:
1. Owner name + role extracted via LLM from site content (free — done in orchestrator)
2. Email extracted from HTML via regex (free — done in email_extractor)
3. LinkedIn extracted from HTML when present (free — done in email_extractor)

V3: Tavily DISABLED — contacts now come from scraping + LLM extraction.
    Tavily removal saves ~$30-100/month and eliminates a dependency.
    TODO: Remove Tavily module entirely after 1 week of stable production.
"""

import asyncio
import json
import re
from typing import Dict, Optional, List
from agents.nodes.utils import get_llm
# TODO: Remove tavily import entirely after confirming stability
# from agents.nodes.utils import get_tavily_client


def _extract_name_from_linkedin_url(url: str) -> Optional[str]:
    """
    Extract a human-readable name from a LinkedIn URL slug.
    E.g. https://linkedin.com/in/nathan-pearce-123abc → "nathan pearce"
    """
    if not url or "linkedin.com/in/" not in url:
        return None
    try:
        # Get the slug after /in/
        slug = url.split("linkedin.com/in/")[1].strip("/").split("?")[0]
        # Remove trailing hash codes (e.g. "-123abc" or "-a1b2c3d4")
        # LinkedIn slugs often end with a hex-like suffix
        slug = re.sub(r'-[a-f0-9]{6,}$', '', slug)
        # Remove pure numeric suffixes (e.g. "-12345")
        slug = re.sub(r'-\d+$', '', slug)
        # Convert hyphens to spaces
        name = slug.replace("-", " ").strip()
        return name if len(name) > 2 else None
    except Exception:
        return None


def _normalize_name_parts(name: str) -> list:
    """
    Normalize a name into lowercase ASCII parts for matching.
    Handles accented characters, hyphens, URL-encoded chars.
    """
    import unicodedata
    nfkd = unicodedata.normalize('NFKD', name)
    ascii_name = nfkd.encode('ASCII', 'ignore').decode('ASCII')
    cleaned = re.sub(r'[^a-z0-9\s]', ' ', ascii_name.lower())
    parts = [p for p in cleaned.split() if len(p) > 1]
    return parts


def _names_match(name1: Optional[str], name2: Optional[str]) -> bool:
    """
    Check if two names refer to the same person.
    Uses containment: all significant parts of the shorter name
    must appear somewhere in the longer string.

    Handles LinkedIn slug formats:
    - "Charlie Casely-Hayford" vs "charlie casely hayford" → True
    - "Lloyd Stratton" vs "lloydstratton" → True
    - "Mark Marengo" vs "markmarengo savilerow bespoke" → True
    - "Erdal Matiloğlu" vs "erdal matilo%C4%9Flu" → True
    - "John Smith" vs "jane doe" → False
    """
    if not name1 or not name2:
        return False

    parts1 = _normalize_name_parts(name1)
    parts2 = _normalize_name_parts(name2)

    if not parts1 or not parts2:
        return False

    # Clean the second name into a single slug for containment check
    slug1 = re.sub(r'[^a-z0-9\s]', ' ', name1.lower())
    slug2 = re.sub(r'[^a-z0-9\s]', ' ', name2.lower())

    # Strategy 1: all parts of name1 found in slug2 (word boundary or substring)
    all_in_slug2 = all(part in slug2 for part in parts1)
    # Strategy 2: all parts of name2 found in slug1
    all_in_slug1 = all(part in slug1 for part in parts2)

    if all_in_slug2 or all_in_slug1:
        return True

    # Strategy 3: set intersection (at least 2 parts match)
    overlap = set(parts1) & set(parts2)
    return len(overlap) >= 2


async def find_contacts_for_brand(
    brand_name: str,
    brand_url: str,
    city: str,
    country: str = "",
    existing_contact: Optional[Dict] = None,
) -> Dict:
    """
    Cascading contact finder. Tries multiple sources to find C-level contacts.
    
    Returns:
        Dict with keys: contact_name, contact_role, contact_email, 
                        contact_phone, contact_linkedin, contact_source
    """
    # If we already have good contact info, skip
    if existing_contact:
        has_name = bool(existing_contact.get("contact_name"))
        has_email = bool(existing_contact.get("contact_email"))
        if has_name and has_email:
            print(f"[CONTACT-FINDER] ✅ {brand_name}: Already have contact info, skipping")
            return existing_contact

    print(f"[CONTACT-FINDER] 🔍 Searching contacts for: {brand_name} ({city})")

    # ================================================================
    # Tavily DISABLED — contacts now come from scraping + LLM extraction.
    # The existing_contact dict already contains owner_name, email, and
    # LinkedIn extracted from the HTML by email_extractor + LLM.
    # ================================================================
    # TODO: Remove _search_tavily_for_contacts entirely after 1 week
    # contact_info = await _search_tavily_for_contacts(brand_name, brand_url, city, country)
    contact_info = _empty_contact()

    # Merge with existing contact info (prefer existing data — already extracted from site)
    if existing_contact:
        for key in ["contact_name", "contact_role", "contact_email", "contact_phone", "contact_linkedin"]:
            if existing_contact.get(key):
                contact_info[key] = existing_contact[key]

    # Cross-validation: ensure name matches LinkedIn profile
    contact_info = _cross_validate_name_linkedin(contact_info, brand_name)

    if contact_info.get("contact_name"):
        linkedin_status = "🔗 LinkedIn ✓" if contact_info.get("contact_linkedin") else "no LinkedIn"
        print(f"[CONTACT-FINDER] ✅ {brand_name}: Found → {contact_info['contact_name']} ({contact_info.get('contact_role', 'N/A')}) [{linkedin_status}]")
    else:
        print(f"[CONTACT-FINDER] ⚠️ {brand_name}: No contacts found")

    return contact_info


def _cross_validate_name_linkedin(contact_info: Dict, brand_name: str) -> Dict:
    """
    Cross-validate that the contact_name matches the LinkedIn profile URL.
    If they don't match, remove the LinkedIn URL to avoid confusion.
    """
    name = contact_info.get("contact_name")
    linkedin = contact_info.get("contact_linkedin")

    if not name or not linkedin:
        return contact_info

    # Extract name from LinkedIn URL
    linkedin_name = _extract_name_from_linkedin_url(linkedin)

    if not linkedin_name:
        # Can't extract name from URL — keep both but log warning
        print(f"[CONTACT-FINDER] ⚠️ {brand_name}: Cannot verify LinkedIn URL format")
        return contact_info

    if _names_match(name, linkedin_name):
        print(f"[CONTACT-FINDER] ✓ {brand_name}: Name '{name}' matches LinkedIn profile '{linkedin_name}'")
        return contact_info
    else:
        # MISMATCH — remove the LinkedIn URL, it's for a different person
        print(f"[CONTACT-FINDER] ✗ {brand_name}: Name MISMATCH — '{name}' ≠ LinkedIn '{linkedin_name}' → removing LinkedIn URL")
        contact_info["contact_linkedin"] = None
        return contact_info


async def _search_tavily_for_contacts(
    brand_name: str,
    brand_url: str,
    city: str,
    country: str,
) -> Dict:
    """
    DEPRECATED: Tavily disabled. This function is dead code kept for reference.
    TODO: Remove entirely after 1 week of stable production.
    """
    return _empty_contact()
    # --- Dead code below (kept for reference) ---
    client = get_tavily_client()  # noqa: F811

    # Extract domain for more targeted searches
    domain = brand_url.replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0]

    # Multiple search queries for better coverage - Priority order
    queries = [
        f'"{brand_name}" {city} LinkedIn "founder" OR "owner" OR "CEO" OR "Managing Director"',
        f'"{brand_name}" {city} LinkedIn "sourcing" OR "production" OR "buyer" OR "tailor" OR "creative director"',
        f'"{brand_name}" {city} who owns founder',
    ]
    if domain:
        queries.append(f'site:linkedin.com "{brand_name}" OR "{domain}" "founder" OR "owner" OR "CEO" OR "sourcing" OR "buyer"')

    all_results = []
    for query in queries:
        try:
            response = client.search(
                query=query,
                search_depth="basic",
                max_results=5,
                include_raw_content=False,
            )
            results = response.get("results", [])
            all_results.extend(results)
        except Exception as e:
            print(f"[CONTACT-FINDER] Tavily search error: {e}")

    if not all_results:
        return _empty_contact()

    # Find LinkedIn profiles — collect ALL of them for cross-validation later
    linkedin_profiles = []
    for r in all_results:
        url = r.get("url", "")
        title = r.get("title", "")
        content = r.get("content", "")
        if "linkedin.com/in/" in url:
            linkedin_profiles.append({
                "url": url,
                "title": title,
                "content": content,
                "name_from_url": _extract_name_from_linkedin_url(url),
            })

    # Pick the best LinkedIn match (prefer the first one for now)
    primary_linkedin = linkedin_profiles[0]["url"] if linkedin_profiles else None

    # Aggregate all search snippets for LLM extraction
    search_context = "\n\n".join([
        f"Source: {r.get('url', '')}\nTitle: {r.get('title', '')}\nContent: {r.get('content', '')[:800]}"
        for r in all_results[:8]
    ])

    # Add LinkedIn profiles context for the LLM
    if linkedin_profiles:
        linkedin_context = "\n\nLINKEDIN PROFILES FOUND:\n" + "\n".join([
            f"  - URL: {p['url']} | Name from URL: {p['name_from_url']} | Title: {p['title']}"
            for p in linkedin_profiles[:5]
        ])
        search_context += linkedin_context

    # ================================================================
    # STEP 2: LLM Extraction — Parse contacts from search results
    # ================================================================
    contact_info = await _extract_contacts_with_llm(
        brand_name, city, search_context, linkedin_profiles, domain
    )

    return contact_info


async def _extract_contacts_with_llm(
    brand_name: str,
    city: str,
    search_context: str,
    linkedin_profiles: List[Dict] = None,
    domain: str = "",
) -> Dict:
    """
    Use GPT to extract structured contact info from search results.
    """
    llm = get_llm(fast=False)  # Use deep model for better extraction

    linkedin_instruction = ""
    if linkedin_profiles:
        linkedin_instruction = f"""
LINKEDIN PROFILES AVAILABLE:
{chr(10).join([f'  - {p["url"]} (name from URL: {p["name_from_url"]})' for p in linkedin_profiles[:5]])}
"""

    prompt = f"""You are a B2B lead intelligence agent specialized in identifying high-value decision-makers for a premium menswear manufacturing company.
Your goal is to extract and validate the BEST possible contact for partnership outreach for each brand.

🎯 OBJECTIVE
Given:
Brand name: {brand_name}
Website domain: {domain}
City: {city}
{linkedin_instruction}

SEARCH RESULTS CONTEXT:
{search_context}

Return: The MOST relevant decision-maker (Founder, Owner, CEO) with HIGH confidence and minimal hallucination.

🧠 STEP 1 — VALIDATE BRAND
First, determine if the brand is valid and relevant. Reject the brand if:
- It does not clearly exist as a real company
- It is a mix of multiple brands or corrupted name
- It is a large global brand unlikely to outsource production
- It is a marketplace, reseller, or multi-brand store
If rejected, set status to "invalid_brand" and provide reason.

🧠 STEP 2 — IDENTIFY COMPANY TYPE
Classify the brand:
"independent_boutique", "atelier_bespoke", "growing_brand", "established_brand", "retailer_multibrand"
Only prioritize: independent_boutique, atelier_bespoke, growing_brand.

🧠 STEP 3 — FIND DECISION MAKERS
Search for people associated with the company in the search context.
Prioritize ONLY:
- Founder
- Co-Founder
- Owner
- CEO (only if small company)
Avoid:
- Designers (unless also founder)
- Creative Directors
- Tailors without ownership role
- Employees

🧠 STEP 4 — MULTI-SOURCE VALIDATION
Each contact MUST be validated using at least 2 sources: Official website, LinkedIn, Press articles.
If only 1 weak source → Lower confidence score.
CRITICAL RULE FOR LINKEDIN:
- You MUST only attach a LinkedIn URL to a contact if the NAME on that LinkedIn profile matches the contact_name you are returning.
- If the LinkedIn profile belongs to someone DIFFERENT than the person you identified as Owner/Founder/CEO, do NOT include it.

🧠 STEP 5 — EMAIL STRATEGY
If an exact direct email is explicitly found in the text, return it.
If you do not find a direct email in the text: DO NOT GUESS OR GENERATE ONE. Leave it as null or empty. It is strictly forbidden to guess emails using domain patterns.

🧠 STEP 6 — CONFIDENCE SCORING
Score from 0 to 1 based on:
+0.4 → Correct role (Founder/Owner)
+0.2 → Appears on official website
+0.2 → LinkedIn match
+0.1 → Location match
+0.1 → Email validity

🧠 STEP 7 — OUTPUT FORMAT
If multiple candidates exist:
- Select the one MOST likely to make partnership decisions
- Not the most visible one

Return ONLY valid JSON:
{{
  "status": "valid" | "invalid_brand",
  "brand": "...",
  "company_type": "...",
  "contact": {{
    "name": "...",
    "title": "...",
    "linkedin": "...",
    "email": "...",
    "email_status": "verified | unverified | generated | not_found"
  }},
  "confidence_score": 0.0,
  "notes": "...",
  "fit_for_lanca": "high | medium | low"
}}

⚠️ STRICT RULES
DO NOT invent people
DO NOT guess roles
DO NOT merge brands
DO NOT return multiple contacts
If unsure → lower confidence instead of guessing

🧠 STRATEGIC THINKING
Prefer: Small, premium, independent brands; Businesses likely to outsource production; Founders still involved in operations.
Avoid: Corporate structures; Large vertical brands; Fast fashion or mass retail.
Quality > Quantity. It is better to return NO contact than a wrong one.
"""

    try:
        response = await llm.ainvoke(prompt)
        raw = response.content.replace("```json", "").replace("```", "").strip()
        result = json.loads(raw)
        
        # Format the result back to what the system expects
        if result.get("status") == "invalid_brand" or not result.get("contact"):
            return _empty_contact()

        contact = result.get("contact", {})
        mapped = {
            "contact_name": contact.get("name"),
            "contact_role": contact.get("title"),
            "contact_email": contact.get("email"),
            "contact_phone": None,
            "contact_linkedin": contact.get("linkedin"),
            "contact_source": "linkedin" if contact.get("linkedin") else "web",
            
            # Additional useful data from the new prompt
            "contact_confidence": result.get("confidence_score", 0.0),
            "contact_notes": result.get("notes"),
            "contact_fit_for_lanca": result.get("fit_for_lanca"),
            "contact_email_status": contact.get("email_status"),
            "contact_company_type": result.get("company_type"),
        }
        
        # Clean null strings
        for key in mapped:
            if mapped[key] in ["null", "None", "", None]:
                mapped[key] = None

        return mapped
    except Exception as e:
        print(f"[CONTACT-FINDER] LLM extraction error: {e}")
        return _empty_contact()



async def find_contacts_batch(
    brands: List[Dict],
    city: str,
    country: str = "",
    max_concurrent: int = 3,
) -> List[Dict]:
    """
    Find contacts for multiple brands with concurrency control.
    """
    semaphore = asyncio.Semaphore(max_concurrent)

    async def find_one(brand: Dict) -> Dict:
        async with semaphore:
            existing = {
                "contact_name": brand.get("contact_name"),
                "contact_role": brand.get("contact_role"),
                "contact_email": brand.get("contact_email"),
                "contact_phone": brand.get("contact_phone"),
                "contact_linkedin": brand.get("contact_linkedin"),
            }
            result = await find_contacts_for_brand(
                brand_name=brand.get("name", ""),
                brand_url=brand.get("website_url", ""),
                city=city,
                country=country,
                existing_contact=existing,
            )
            # Merge back into brand
            brand.update({k: v for k, v in result.items() if v is not None})
            return brand

    tasks = [find_one(b) for b in brands]
    return await asyncio.gather(*tasks)


def _empty_contact(linkedin_url: Optional[str] = None) -> Dict:
    """Return empty contact dict."""
    return {
        "contact_name": None,
        "contact_role": None,
        "contact_email": None,
        "contact_phone": None,
        "contact_linkedin": linkedin_url,
        "contact_source": "not_found",
    }
