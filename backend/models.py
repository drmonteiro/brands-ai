"""
Pydantic models for the Confeções Lança prospector
"""

import json
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
from typing import Optional, List, Dict, Any
from enum import Enum

from services.currency import get_eur_usd_rate, eur_to_usd, usd_to_eur


# ============================================================================
# ENUMS
# ============================================================================

class ProspectStatus(str, Enum):
    NEW = "new"
    CONTACTED = "contacted"
    CONVERTED = "converted"
    REJECTED = "rejected"


class SortOrder(str, Enum):
    ASC = "asc"
    DESC = "desc"


class SortField(str, Enum):
    FINAL_SCORE = "final_score"
    STORE_COUNT = "store_count"
    AVG_PRICE = "avg_suit_price_eur"
    DISCOVERED_AT = "discovered_at"
    NAME = "name"


class PriceRange(str, Enum):
    ALL = "all"
    UNDER_500 = "under_500"
    RANGE_500_1000 = "500_1000"
    RANGE_1000_2000 = "1000_2000"
    OVER_2000 = "over_2000"
    NO_PRICE = "no_price"


class StoreSize(str, Enum):
    ALL = "all"
    BOUTIQUE = "boutique"
    MEDIUM = "medium"
    LARGE = "large"


# ============================================================================
# FILTER MODELS
# ============================================================================

class ProspectFilters(BaseModel):
    city: Optional[str] = None
    country: Optional[str] = None
    country_code: Optional[str] = None
    min_stores: Optional[int] = Field(None, ge=0)
    max_stores: Optional[int] = Field(None, ge=0)
    store_size: Optional[StoreSize] = None
    min_price: Optional[float] = Field(None, ge=0)
    max_price: Optional[float] = Field(None, ge=0)
    price_range: Optional[PriceRange] = None
    min_score: Optional[float] = Field(None, ge=0, le=100)
    max_score: Optional[float] = Field(None, ge=0, le=100)
    status: Optional[ProspectStatus] = None
    statuses: Optional[List[ProspectStatus]] = None
    brand_style: Optional[str] = None
    brand_styles: Optional[List[str]] = None
    business_model: Optional[str] = None
    made_to_measure: Optional[str] = None
    wool_percentage: Optional[str] = None
    search_name: Optional[str] = None
    sort_by: SortField = SortField.FINAL_SCORE
    sort_order: SortOrder = SortOrder.DESC
    limit: int = Field(25, ge=1, le=100)
    offset: int = Field(0, ge=0)


# ============================================================================
# BRAND LEAD MODEL
# ============================================================================

class BrandLead(BaseModel):
    """Schema for a discovered brand lead."""
    model_config = ConfigDict(populate_by_name=True)

    id: Optional[str] = None
    name: str
    website_url: str = Field(alias="websiteUrl")
    store_count: int = Field(ge=0, default=0, alias="storeCount")
    average_suit_price_usd: float = Field(ge=0, default=0, alias="averageSuitPriceUSD")
    city: Optional[str] = None
    origin_country: str = Field(default="Unknown", alias="originCountry")
    verified: bool = False

    # Pricing
    avg_suit_price_eur: Optional[float] = Field(default=None)
    price_note: Optional[str] = Field(default=None, alias="priceNote")

    # Quality attributes
    wool_percentage: Optional[str] = Field(default=None, alias="woolPercentage")
    made_to_measure: Optional[bool] = Field(default=None, alias="madeToMeasure")

    # Brand classification
    brand_style: Optional[str] = Field(None, alias="brandStyle")
    business_model: Optional[str] = Field(None, alias="businessModel")

    # Descriptions
    company_overview: Optional[str] = Field(None, alias="companyOverview")
    detailed_description: Optional[str] = Field(None, alias="detailedDescription")

    # Location
    store_locations: Optional[List[str]] = Field(default_factory=list, alias="storeLocations")
    headquarters_address: Optional[str] = Field(None, alias="headquartersAddress")
    headquarters_city: Optional[str] = Field(None, alias="headquartersCity")
    headquarters_confidence: Optional[str] = Field("unknown", alias="headquartersConfidence")
    local_store_address: Optional[str] = Field(None, alias="localStoreAddress")
    city_presence_type: Optional[str] = Field("unknown", alias="cityPresenceType")
    store_count_confidence: Optional[str] = Field("unknown", alias="storeCountConfidence")

    # Scoring
    fit_score: Optional[int] = Field(default=0, alias="fitScore")
    similarity_failed: Optional[bool] = Field(default=None, alias="similarityFailed")

    # Contact (populated by Google Places or future enrichment)
    contact_name: Optional[str] = Field(None, alias="contactName")
    contact_email: Optional[str] = Field(None, alias="contactEmail")
    contact_phone: Optional[str] = Field(None, alias="contactPhone")

    # DB compat fields
    material_composition: Optional[List[str]] = Field(default_factory=list, alias="materialComposition")

    @field_validator("made_to_measure", mode="before")
    @classmethod
    def coerce_llm_booleans(cls, v):
        if v is None:
            return None
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            s = v.strip().lower()
            if s in ("true", "1", "yes"):
                return True
            if s in ("false", "0", "no"):
                return False
            return None
        return v

    @field_validator("fit_score", mode="before")
    @classmethod
    def coerce_fit_score(cls, v):
        if v is None:
            return 0
        try:
            return int(v)
        except (TypeError, ValueError):
            return 0

    @field_validator("store_count", mode="before")
    @classmethod
    def coerce_store_count(cls, v):
        if v is None:
            return 0
        try:
            return int(v)
        except (TypeError, ValueError):
            return 0

    @field_validator("average_suit_price_usd", mode="before")
    @classmethod
    def coerce_avg_price_usd(cls, v):
        if v is None:
            return 0
        try:
            return max(0.0, float(v))
        except (TypeError, ValueError):
            return 0

    @field_validator('store_locations', 'material_composition', mode='before')
    @classmethod
    def parse_json_fields(cls, v):
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
            except Exception:
                pass
            if v.strip():
                return [v]
            return []
        return v or []

    def model_post_init(self, __context):
        rate = get_eur_usd_rate()
        if (self.average_suit_price_usd == 0) and self.avg_suit_price_eur is not None:
            self.average_suit_price_usd = eur_to_usd(self.avg_suit_price_eur, rate)
        if self.avg_suit_price_eur is None and self.average_suit_price_usd > 0:
            self.avg_suit_price_eur = usd_to_eur(self.average_suit_price_usd, rate)


# ============================================================================
# WORKFLOW STATE & REQUEST MODELS
# ============================================================================

class ProspectorState(BaseModel):
    """State for the prospecting agent workflow."""
    target_city: str
    target_country: str = ""
    exchange_rate: float = Field(default_factory=get_eur_usd_rate)
    search_results_raw: List[Dict] = Field(default_factory=list)
    filtered_brands: List[Dict] = Field(default_factory=list)
    enriched_brands: List[Dict] = Field(default_factory=list)
    verified_brands: List[BrandLead] = Field(default_factory=list)
    progress: List[str] = Field(default_factory=list)
    error: Optional[str] = None


class SearchRequest(BaseModel):
    """Request body for prospect search."""
    city: str
    force_refresh: bool = Field(default=False)


class ApprovalRequest(BaseModel):
    """Request body for email approval."""
    model_config = ConfigDict(populate_by_name=True)

    brand_name: str = Field(alias="brandName")
    brand_data: Dict[str, Any] = Field(alias="brandData")


class ProgressMessage(BaseModel):
    """SSE progress message."""
    type: str
    message: Optional[str] = None
    timestamp: str
    verified_brands: Optional[List[BrandLead]] = None
