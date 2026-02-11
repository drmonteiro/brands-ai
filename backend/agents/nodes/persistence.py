"""
Node 4: Persistence Node
Finalizes selected brands and saves them to PostgreSQL with full scoring.
"""
from typing import List, Dict, Any, Union
from models import ProspectorState, BrandLead
from services.database import save_prospect, get_existing_urls_for_city
from services.vector_db import calculate_prospect_score
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
            duplicate_count += 1
            continue
        
        # Build BrandLead object and dict
        if hasattr(brand, "model_dump"):
            brand_obj, brand_dict = brand, brand.model_dump()
        else:
            brand_obj, brand_dict = BrandLead(**brand), brand
            
        prospect_dict = {
            "name": brand_dict["name"],
            "website_url": brand_dict.get("websiteUrl") or brand_dict.get("website_url"),
            "city": target_city,
            "country": brand_dict.get("originCountry") or brand_dict.get("origin_country"),
            "country_code": "XX", # Placeholder
            "store_count": brand_dict.get("storeCount") or brand_dict.get("store_count", 1),
            "avg_suit_price_eur": (brand_dict.get("averageSuitPriceUSD") or brand_dict.get("average_suit_price_usd", 0)) / 1.08,
            "brand_style": brand_dict.get("brandStyle") or brand_dict.get("brand_style", "unknown"),
            "business_model": brand_dict.get("businessModel") or brand_dict.get("business_model", "unknown"),
            "description": brand_dict.get("companyOverview") or brand_dict.get("company_overview", ""),
            "detailed_description": brand_dict.get("detailedDescription") or brand_dict.get("detailed_description", ""),
            "store_locations": brand_dict.get("storeLocations") or brand_dict.get("store_locations", []),
            "fit_score": brand_dict.get("fitScore") or brand_dict.get("fit_score", 0),
            "material_composition": [brand_dict.get("woolPercentage") or brand_dict.get("wool_percentage")] if (brand_dict.get("woolPercentage") or brand_dict.get("wool_percentage")) else [],
            "made_to_measure": brand_dict.get("madeToMeasure") or brand_dict.get("made_to_measure", False),
        }
        
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
