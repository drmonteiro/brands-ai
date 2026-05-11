"""
Node 4: Persistence Node
Finalizes selected brands and saves them to PostgreSQL with full scoring.
Includes Contact Finder cascade for C-level discovery.
"""
import logging
from typing import List, Dict, Any, Union
from models import ProspectorState, BrandLead
from services.database import save_prospect, get_existing_urls_for_city, get_prospect_id_by_url, update_prospect_contact
from services.scoring import calculate_prospect_score
from services.contact_finder import find_contacts_for_brand
from .utils import normalize_url

logger = logging.getLogger("node.persistence")

# ============================================================================
# COUNTRY NAME → ISO CODE MAPPING
# Fixes the "XX" placeholder that broke market_score for ALL brands.
# ============================================================================
COUNTRY_TO_CODE = {
    # Europe
    "united kingdom": "GB", "uk": "GB", "england": "GB", "scotland": "GB", "wales": "GB",
    "france": "FR", "germany": "DE", "italy": "IT", "italia": "IT",
    "spain": "ES", "españa": "ES", "portugal": "PT",
    "netherlands": "NL", "holland": "NL", "belgium": "BE", "belgique": "BE",
    "switzerland": "CH", "sweden": "SE", "denmark": "DK",
    "norway": "NO", "finland": "FI", "ireland": "IE",
    "austria": "AT", "greece": "GR", "romania": "RO",
    "czech republic": "CZ", "czechia": "CZ", "poland": "PL",
    "hungary": "HU", "croatia": "HR", "luxembourg": "LU",
    # Americas
    "united states": "US", "usa": "US", "us": "US",
    "canada": "CA", "mexico": "MX", "méxico": "MX",
    "brazil": "BR", "brasil": "BR", "colombia": "CO",
    "peru": "PE", "argentina": "AR", "chile": "CL",
    # Asia & Middle East
    "japan": "JP", "south korea": "KR", "china": "CN", "india": "IN",
    "singapore": "SG", "hong kong": "HK", "turkey": "TR", "türkiye": "TR",
    "uae": "AE", "united arab emirates": "AE", "saudi arabia": "SA",
    "qatar": "QA", "bahrain": "BH", "kuwait": "KW",
    # Oceania & Africa
    "australia": "AU", "new zealand": "NZ", "angola": "AO",
    "south africa": "ZA", "nigeria": "NG", "morocco": "MA",
    # Aliases
    "international": "XX",
}


def _resolve_country_code(country_name: str) -> str:
    """Resolve a country name to its ISO 3166-1 alpha-2 code."""
    if not country_name:
        return "XX"
    return COUNTRY_TO_CODE.get(country_name.lower().strip(), "XX")

async def filter_node(state: Union[ProspectorState, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Finalize the selected brands and save to PostgreSQL database.
    """
    target_city = state.target_city if hasattr(state, "target_city") else state.get("target_city")
    potential_brands = state.potential_brands if hasattr(state, "potential_brands") else state.get("potential_brands", [])
    exchange_rate = state.exchange_rate if hasattr(state, "exchange_rate") else state.get("exchange_rate", 1.08)
    
    logger.info("┌─── NODE 4: PERSISTENCE ───────────────────────────")
    logger.info("│ Brands to save: %d for %s", len(potential_brands), target_city)
    new_progress = []
    
    if not potential_brands:
        logger.info("│ No brands to save — finishing")
        logger.info("└──────────────────────────────────────────────────")
        return {"verified_brands": [], "progress": ["🎯 RESULTADO FINAL: 0 marcas encontradas"]}
    
    existing_urls = await get_existing_urls_for_city(target_city)
    logger.info("│ Existing URLs in DB for %s: %d", target_city, len(existing_urls))
    new_progress.append(f"\n💾 Guardando {len(potential_brands)} marcas na base de dados...")
    
    saved_count, duplicate_count, verified_brands = 0, 0, []
    
    for brand in potential_brands:
        url = brand.website_url if hasattr(brand, "website_url") else brand.get("website_url")
        norm_url = normalize_url(url)
        
        if norm_url in existing_urls:
            # [V3] Enrichment: even if duplicate, search for contacts if missing
            try:
                # Extract brand info directly from the brand object (not prospect_dict which isn't defined yet)
                brand_name = brand.name if hasattr(brand, "name") else brand.get("name", "Unknown")
                brand_url = brand.website_url if hasattr(brand, "website_url") else brand.get("website_url", url)
                brand_country = brand.origin_country if hasattr(brand, "origin_country") else brand.get("origin_country", "")
                
                existing_contact = {
                    "contact_name": getattr(brand, "contact_name", None) if hasattr(brand, "contact_name") else brand.get("contact_name"),
                    "contact_role": getattr(brand, "contact_role", None) if hasattr(brand, "contact_role") else brand.get("contact_role"),
                    "contact_email": getattr(brand, "contact_email", None) if hasattr(brand, "contact_email") else brand.get("contact_email"),
                    "contact_phone": getattr(brand, "contact_phone", None) if hasattr(brand, "contact_phone") else brand.get("contact_phone"),
                    "contact_linkedin": getattr(brand, "contact_linkedin", None) if hasattr(brand, "contact_linkedin") else brand.get("contact_linkedin"),
                }
                
                # Check if we should find contacts (cascade)
                contact_result = await find_contacts_for_brand(
                    brand_name=brand_name,
                    brand_url=brand_url,
                    city=target_city,
                    country=brand_country,
                    existing_contact=existing_contact,
                )
                
                # If we found something new, update only the contact info
                if any(contact_result.get(k) and not existing_contact.get(k) for k in contact_result):
                    p_id = await get_prospect_id_by_url(brand_url)
                    if p_id:
                        await update_prospect_contact(p_id, contact_result)
                        new_progress.append(f"   👤 {brand_name}: Contactos actualizados")
            except Exception as e:
                brand_name_safe = brand.name if hasattr(brand, "name") else brand.get("name", "Unknown")
                logger.warning("│ Contact enrichment error for %s: %s", brand_name_safe, e)
            
            duplicate_count += 1
            continue
        
        # Build BrandLead object and dict
        if hasattr(brand, "model_dump"):
            brand_obj, brand_dict = brand, brand.model_dump()
        else:
            brand_obj, brand_dict = BrandLead(**brand), brand
            
        # Build initial prospect dict
        # Owner name from LLM extraction takes precedence for contact_name
        owner_name = brand_dict.get("ownerName") or brand_dict.get("owner_name")
        owner_role = brand_dict.get("ownerRole") or brand_dict.get("owner_role")

        prospect_dict = {
            "name": brand_dict["name"],
            "website_url": brand_dict.get("websiteUrl") or brand_dict.get("website_url"),
            "city": target_city,
            "country": brand_dict.get("originCountry") or brand_dict.get("origin_country"),
            "country_code": _resolve_country_code(brand_dict.get("originCountry") or brand_dict.get("origin_country", "")),
            "store_count": brand_dict.get("storeCount") or brand_dict.get("store_count", 1),
            "avg_suit_price_eur": float(brand_dict.get("averageSuitPriceUSD") or brand_dict.get("average_suit_price_usd") or 0) / exchange_rate,
            "brand_style": brand_dict.get("brandStyle") or brand_dict.get("brand_style", "unknown"),
            "business_model": brand_dict.get("businessModel") or brand_dict.get("business_model", "unknown"),
            "description": brand_dict.get("companyOverview") or brand_dict.get("company_overview", ""),
            "detailed_description": brand_dict.get("detailedDescription") or brand_dict.get("detailed_description", ""),
            "store_locations": brand_dict.get("storeLocations") or brand_dict.get("store_locations", []),
            "fit_score": (
                brand_dict.get("fitScore")
                if brand_dict.get("fitScore") is not None
                else brand_dict.get("fit_score", 0)
            ),
            "material_composition": (
                [brand_dict.get("woolPercentage")]
                if brand_dict.get("woolPercentage") is not None
                and brand_dict.get("woolPercentage") != ""
                else (
                    [brand_dict.get("wool_percentage")]
                    if brand_dict.get("wool_percentage") is not None
                    and brand_dict.get("wool_percentage") != ""
                    else []
                )
            ),
            "made_to_measure": (
                brand_dict["madeToMeasure"]
                if "madeToMeasure" in brand_dict
                else brand_dict.get("made_to_measure")
            ),
            "contact_name": brand_dict.get("contactName") or brand_dict.get("contact_name") or owner_name,
            "contact_role": brand_dict.get("contactRole") or brand_dict.get("contact_role") or owner_role,
            "contact_email": brand_dict.get("contactEmail") or brand_dict.get("contact_email"),
            "contact_phone": brand_dict.get("contactPhone") or brand_dict.get("contact_phone"),
            "contact_linkedin": brand_dict.get("contactLinkedin") or brand_dict.get("contact_linkedin"),
            "headquarters_address": brand_dict.get("headquartersAddress") or brand_dict.get("headquarters_address"),
            "price_note": brand_dict.get("priceNote") or brand_dict.get("price_note"),
            "product_images": brand_dict.get("productImages") or brand_dict.get("product_images", []),
            "city_presence_type": brand_dict.get("city_presence_type")
            or brand_dict.get("cityPresenceType")
            or "unknown",
            "wool_percentage": (
                brand_dict.get("woolPercentage")
                if "woolPercentage" in brand_dict
                else brand_dict.get("wool_percentage")
            ),
        }
        
        # ============================================================
        # CONTACT FINDER CASCADE — Search LinkedIn/Google for C-levels
        # ============================================================
        try:
            existing_contact = {
                "contact_name": prospect_dict.get("contact_name"),
                "contact_role": prospect_dict.get("contact_role"),
                "contact_email": prospect_dict.get("contact_email"),
                "contact_phone": prospect_dict.get("contact_phone"),
                "contact_linkedin": prospect_dict.get("contact_linkedin"),
            }
            contact_result = await find_contacts_for_brand(
                brand_name=prospect_dict["name"],
                brand_url=prospect_dict["website_url"],
                city=target_city,
                country=prospect_dict.get("country", ""),
                existing_contact=existing_contact,
            )
            # Merge contact results into prospect
            for key in ["contact_name", "contact_role", "contact_email", "contact_phone", "contact_linkedin"]:
                if contact_result.get(key):
                    prospect_dict[key] = contact_result[key]
            new_progress.append(f"   👤 {prospect_dict['name']}: {contact_result.get('contact_name', '?')} ({contact_result.get('contact_role', '?')})")
        except Exception as e:
            logger.warning("│ Contact finder error for %s: %s", prospect_dict["name"], e)
        
        try:
            scores, similar_clients = await calculate_prospect_score(prospect_dict)
            result = await save_prospect(prospect=prospect_dict, city=target_city, scores=scores, similar_clients=similar_clients)
            
            if result["status"] == "saved":
                saved_count += 1
                existing_urls.add(norm_url)
                verified_brands.append(brand_obj)
                logger.info("│ SAVED: %s (%s) — score=%.0f", prospect_dict["name"], prospect_dict["website_url"], scores.get("final_score", 0) if isinstance(scores, dict) else 0)
        except Exception as e:
            logger.error("│ Error saving %s: %s", brand_dict.get("name"), e)
    
    # Cap output at 30 brands, minimum threshold 55/100
    MAX_OUTPUT_BRANDS = 30
    MIN_SCORE_THRESHOLD = 55
    if len(verified_brands) > MAX_OUTPUT_BRANDS:
        verified_brands = verified_brands[:MAX_OUTPUT_BRANDS]
        logger.info("│ Capped to %d brands", MAX_OUTPUT_BRANDS)

    logger.info("│ Results: %d saved, %d duplicates skipped", saved_count, duplicate_count)
    logger.info("│ FINAL: %d verified brands", len(verified_brands))
    logger.info("└──────────────────────────────────────────────────")
    new_progress.append(f"   ✅ Guardados: {saved_count} novos")
    if duplicate_count > 0:
        new_progress.append(f"   ⏭️ Duplicados ignorados: {duplicate_count}")
    new_progress.append(f"\n🎯 RESULTADO FINAL: {len(verified_brands)} marcas encontradas")

    return {
        "verified_brands": verified_brands,
        "progress": new_progress,
    }
