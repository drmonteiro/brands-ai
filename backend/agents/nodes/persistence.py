"""
Node 4: Persistence Node
Finalizes selected brands and saves them to PostgreSQL with full scoring.
Includes Contact Finder cascade for C-level discovery.
"""
from typing import List, Dict, Any, Union
from models import ProspectorState, BrandLead
from services.database import save_prospect, get_existing_urls_for_city, get_prospect_id_by_url, update_prospect_contact
from services.vector_db import calculate_prospect_score
from services.contact_finder import find_contacts_for_brand
from .utils import normalize_url

async def filter_node(state: Union[ProspectorState, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Finalize the selected brands and save to PostgreSQL database.
    """
    target_city = state.target_city if hasattr(state, "target_city") else state.get("target_city")
    potential_brands = state.potential_brands if hasattr(state, "potential_brands") else state.get("potential_brands", [])
    
    print(f"[FILTER] Saving {len(potential_brands)} brands for {target_city}...")
    new_progress = []
    
    if not potential_brands:
        return {"verified_brands": [], "progress": ["🎯 RESULTADO FINAL: 0 marcas encontradas"]}
    
    existing_urls = await get_existing_urls_for_city(target_city)
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
                print(f"[PERSISTENCE] Enrichment error for {brand_name_safe}: {e}")
            
            duplicate_count += 1
            continue
        
        # Build BrandLead object and dict
        if hasattr(brand, "model_dump"):
            brand_obj, brand_dict = brand, brand.model_dump()
        else:
            brand_obj, brand_dict = BrandLead(**brand), brand
            
        # Build initial prospect dict
        prospect_dict = {
            "name": brand_dict["name"],
            "website_url": brand_dict.get("websiteUrl") or brand_dict.get("website_url"),
            "city": target_city,
            "country": brand_dict.get("originCountry") or brand_dict.get("origin_country"),
            "country_code": "XX", # Placeholder
            "store_count": brand_dict.get("storeCount") or brand_dict.get("store_count", 1),
            "avg_suit_price_eur": float(brand_dict.get("averageSuitPriceUSD") or brand_dict.get("average_suit_price_usd") or 0) / 1.08,
            "brand_style": brand_dict.get("brandStyle") or brand_dict.get("brand_style", "unknown"),
            "business_model": brand_dict.get("businessModel") or brand_dict.get("business_model", "unknown"),
            "description": brand_dict.get("companyOverview") or brand_dict.get("company_overview", ""),
            "detailed_description": brand_dict.get("detailedDescription") or brand_dict.get("detailed_description", ""),
            "store_locations": brand_dict.get("storeLocations") or brand_dict.get("store_locations", []),
            "fit_score": brand_dict.get("fitScore") or brand_dict.get("fit_score", 0),
            "material_composition": [brand_dict.get("woolPercentage") or brand_dict.get("wool_percentage")] if (brand_dict.get("woolPercentage") or brand_dict.get("wool_percentage")) else [],
            "made_to_measure": brand_dict.get("madeToMeasure") or brand_dict.get("made_to_measure", False),
            "contact_name": brand_dict.get("contactName") or brand_dict.get("contact_name"),
            "contact_role": brand_dict.get("contactRole") or brand_dict.get("contact_role"),
            "contact_email": brand_dict.get("contactEmail") or brand_dict.get("contact_email"),
            "contact_phone": brand_dict.get("contactPhone") or brand_dict.get("contact_phone"),
            "contact_linkedin": brand_dict.get("contactLinkedin") or brand_dict.get("contact_linkedin"),
            "headquarters_address": brand_dict.get("headquartersAddress") or brand_dict.get("headquarters_address"),
            "price_note": brand_dict.get("priceNote") or brand_dict.get("price_note"),
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
            print(f"[CONTACT-FINDER] Error for {prospect_dict['name']}: {e}")
        
        try:
            scores, similar_clients = await calculate_prospect_score(prospect_dict)
            result = await save_prospect(prospect=prospect_dict, city=target_city, scores=scores, similar_clients=similar_clients)
            
            if result["status"] == "saved":
                saved_count += 1
                existing_urls.add(norm_url)
                verified_brands.append(brand_obj)
        except Exception as e:
            print(f"[FILTER] Error saving {brand_dict.get('name')}: {e}")
    
    new_progress.append(f"   ✅ Guardados: {saved_count} novos")
    if duplicate_count > 0: new_progress.append(f"   ⏭️ Duplicados ignorados: {duplicate_count}")
    new_progress.append(f"\n🎯 RESULTADO FINAL: {len(verified_brands)} marcas encontradas")
    
    return {
        "verified_brands": verified_brands,
        "progress": new_progress,
    }
