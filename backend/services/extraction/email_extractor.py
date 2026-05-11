"""
Email & LinkedIn Extractor — Zero-cost extraction from HTML already in memory.

Replaces Tavily for contact discovery. Extracts:
- Emails from mailto links, plain text, and obfuscated patterns
- LinkedIn URLs from social links in footer/header/contact pages

Cost: zero (regex on HTML already scraped by Crawl4AI).
"""

import re
import logging
from urllib.parse import urlparse
from pydantic import BaseModel, Field
from typing import Optional, List

logger = logging.getLogger(__name__)

EMAIL_REGEX = re.compile(
    r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
)

MAILTO_REGEX = re.compile(
    r'mailto:([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,})'
)

OBFUSCATED_REGEX = re.compile(
    r'([A-Za-z0-9._%+-]+)\s*[\[\(]at[\]\)]\s*'
    r'([A-Za-z0-9.-]+)\s*[\[\(]dot[\]\)]\s*([A-Za-z]{2,})',
    re.IGNORECASE
)

LINKEDIN_REGEX = re.compile(
    r'https?://(?:www\.)?linkedin\.com/(?:in|company)/([a-zA-Z0-9_-]+)',
    re.IGNORECASE
)

EXCLUDED_PATTERNS = {
    'noreply@', 'no-reply@', 'mailer-daemon@', 'postmaster@',
    'webmaster@', 'support@shopify', 'email@example',
    'woocommerce@', 'wordpress@', 'privacy@', 'abuse@',
    'hostmaster@', 'info@shopify', 'help@shopify',
    'sentry@', 'cdn-cgi@', 'example@',
}

PRIORITY_PATTERNS = [
    # Priority 1: personal emails (first.last@)
    (re.compile(r'^[a-z]+\.[a-z]+@'), 'personal', 1),
    (re.compile(r'^[a-z]{2,}@(?!info|contact|shop|hello|enquiries|sales|press|orders)'), 'personal', 1),

    # Priority 2: management/director emails
    (re.compile(r'^(ceo|owner|director|founder|gérant|patron|management|direction|admin)@'), 'management', 2),

    # Priority 3: generic commercial emails
    (re.compile(r'^(info|contact|hello|enquiries|sales|enquiry)@'), 'generic', 3),

    # Priority 4: department emails
    (re.compile(r'^(shop|store|boutique|orders|press|marketing|hr|support)@'), 'department', 4),
]


class EmailResult(BaseModel):
    email: str = Field(description="The contact email")
    priority: int = Field(description="1=personal, 2=management, 3=generic, 4=department")
    category: str = Field(description="personal, management, generic, department")
    source: str = Field(description="website_mailto, website_text, website_obfuscated")
    is_own_domain: bool = Field(description="True if email domain matches the boutique domain")


def extract_emails_from_html(
    cleaned_html: str,
    domain: str,
) -> List[EmailResult]:
    """
    Extract and classify emails from HTML already in memory.
    Cost: zero. Time: ~2ms per page.
    """
    if not cleaned_html:
        return []

    site_domain = domain.lower().replace("www.", "")

    # 1. Mailto links (most reliable)
    mailtos = MAILTO_REGEX.findall(cleaned_html)
    mailto_set = {(e.lower(), "website_mailto") for e in mailtos}

    # 2. Plain text
    text_emails = EMAIL_REGEX.findall(cleaned_html)
    text_set = {(e.lower(), "website_text") for e in text_emails}

    # 3. Obfuscated ([at], [dot])
    obfuscated = OBFUSCATED_REGEX.findall(cleaned_html)
    obfuscated_set = {
        (f"{m[0]}@{m[1]}.{m[2]}".lower(), "website_obfuscated")
        for m in obfuscated
    }

    # Unify (mailto takes precedence for source attribution)
    all_emails = {}
    for email, source in list(obfuscated_set) + list(text_set) + list(mailto_set):
        all_emails[email] = source

    # 4. Filter junk
    results = []
    for email, source in all_emails.items():
        if any(excl in email for excl in EXCLUDED_PATTERNS):
            continue
        if not re.match(r'^[a-z0-9]', email):
            continue
        # Skip image file extensions that regex might catch
        if email.endswith(('.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp')):
            continue

        priority = 5
        category = "unknown"
        for pattern, cat, prio in PRIORITY_PATTERNS:
            if pattern.match(email):
                priority = prio
                category = cat
                break

        is_own = site_domain in email

        results.append(EmailResult(
            email=email,
            priority=priority,
            category=category,
            source=source,
            is_own_domain=is_own,
        ))

    results.sort(key=lambda r: (not r.is_own_domain, r.priority))
    return results


def get_best_email(
    all_page_emails: List[EmailResult],
) -> Optional[EmailResult]:
    """Return the best email across all scraped pages."""
    if not all_page_emails:
        return None

    seen = set()
    unique = []
    for e in all_page_emails:
        if e.email not in seen:
            seen.add(e.email)
            unique.append(e)

    unique.sort(key=lambda r: (not r.is_own_domain, r.priority))
    return unique[0] if unique else None


def extract_linkedin_from_html(cleaned_html: str) -> Optional[str]:
    """Extract LinkedIn URL from HTML if present."""
    if not cleaned_html:
        return None

    matches = LINKEDIN_REGEX.findall(cleaned_html)
    if not matches:
        return None

    # Prefer /company/ over /in/ (company page is more useful for outreach)
    for match in matches:
        if f"company/{match}" in cleaned_html.lower():
            return f"https://linkedin.com/company/{match}"

    return f"https://linkedin.com/in/{matches[0]}"
