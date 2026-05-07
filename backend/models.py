"""
Pydantic models for the Confeções Lança prospector
"""

import json
from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Optional, List, Dict, Any
from enum import Enum


# ============================================================================
# ENUMS
# ============================================================================

class ProspectStatus(str, Enum):
    """Status of a prospect in the pipeline"""
    NEW = "new"
    CONTACTED = "contacted"
    CONVERTED = "converted"
    REJECTED = "rejected"


class SortOrder(str, Enum):
    """Sort order for queries"""
    ASC = "asc"
    DESC = "desc"


class SortField(str, Enum):
    """Available fields for sorting"""
    FINAL_SCORE = "final_score"
    STORE_COUNT = "store_count"
    AVG_PRICE = "avg_suit_price_eur"
    DISCOVERED_AT = "discovered_at"
    NAME = "name"
    QUALITY_SCORE = "quality_score"
    SIMILARITY_SCORE = "similarity_score"


class PriceRange(str, Enum):
    """Predefined price ranges"""
    ALL = "all"
    UNDER_500 = "under_500"
    RANGE_500_1000 = "500_1000"
    RANGE_1000_2000 = "1000_2000"
    OVER_2000 = "over_2000"
    NO_PRICE = "no_price"


class StoreSize(str, Enum):
    """Store size categories"""
    ALL = "all"
    BOUTIQUE = "boutique"  # 1-5 stores
    MEDIUM = "medium"      # 6-20 stores
    LARGE = "large"        # 20+ stores


# ============================================================================
# FILTER MODELS
# ============================================================================

class ProspectFilters(BaseModel):
    """Advanced filters for prospect queries"""
    # Location
    city: Optional[str] = None
    country: Optional[str] = None
    country_code: Optional[str] = None
    
    # Store count
    min_stores: Optional[int] = Field(None, ge=0)
    max_stores: Optional[int] = Field(None, ge=0)
    store_size: Optional[StoreSize] = None
    
    # Price (EUR)
    min_price: Optional[float] = Field(None, ge=0)
    max_price: Optional[float] = Field(None, ge=0)
    price_range: Optional[PriceRange] = None
    
    # Scores
    min_score: Optional[float] = Field(None, ge=0, le=100)
    max_score: Optional[float] = Field(None, ge=0, le=100)
    min_quality_score: Optional[float] = Field(None, ge=0, le=100)
    min_similarity_score: Optional[float] = Field(None, ge=0, le=100)
    
    # Categorical
    status: Optional[ProspectStatus] = None
    statuses: Optional[List[ProspectStatus]] = None
    brand_style: Optional[str] = None
    brand_styles: Optional[List[str]] = None
    business_model: Optional[str] = None
    made_to_measure: Optional[str] = None  # "true", "false", "unknown"
    wool_percentage: Optional[str] = None
    
    # Text search
    search_name: Optional[str] = None
    
    # Similar client
    similar_to_client: Optional[str] = None
    
    # Sorting
    sort_by: SortField = SortField.FINAL_SCORE
    sort_order: SortOrder = SortOrder.DESC
    
    # Pagination
    limit: int = Field(25, ge=1, le=100)
    offset: int = Field(0, ge=0)


class QuickFilter(BaseModel):
    """Quick filter presets for common use cases"""
    name: str
    description: str
    filters: ProspectFilters


# ============================================================================
# PROSPECTOR CONFIGURATION
# ============================================================================

class ProspectorConfig(BaseModel):
    """Configuration for the prospector agent"""
    # Price thresholds
    min_price_eur: float = Field(500, ge=0, description="Minimum suit price in EUR")
    max_price_eur: Optional[float] = Field(None, ge=0, description="Maximum suit price in EUR")
    
    # Store limits
    max_stores: int = Field(20, ge=1, description="Maximum number of stores (Lança prefers small boutiques)")
    ideal_max_stores: int = Field(5, ge=1, description="Ideal maximum stores for top scoring")
    
    # Score weights (must sum to 1.0)
    weight_size: float = Field(0.25, ge=0, le=1)
    weight_quality: float = Field(0.30, ge=0, le=1)
    weight_similarity: float = Field(0.30, ge=0, le=1)
    weight_market: float = Field(0.15, ge=0, le=1)
    
    # Search configuration
    queries_per_search: int = Field(3, ge=1, le=10)
    results_per_query: int = Field(20, ge=5, le=50)
    max_candidates: int = Field(15, ge=5, le=50)
    
    # Quality preferences
    prefer_100_wool: bool = True
    prefer_made_to_measure: bool = True
    prefer_heritage_brands: bool = True


class SearchConfigRequest(BaseModel):
    """Request body for configured prospect search"""
    city: str
    config: Optional[ProspectorConfig] = None


# ============================================================================
# BRAND LEAD MODEL
# ============================================================================

class BrandLead(BaseModel):
    """Schema for a discovered brand lead"""
    model_config = ConfigDict(populate_by_name=True)

    id: Optional[str] = None
    name: str
    website_url: str = Field(alias="websiteUrl")
    store_count: int = Field(ge=0, default=1, alias="storeCount")
    average_suit_price_usd: float = Field(ge=0, default=0, alias="averageSuitPriceUSD")
    city: Optional[str] = None
    origin_country: str = Field(default="USA", alias="originCountry")
    verified: bool = False
    verification_log: Optional[List[str]] = Field(default_factory=list, alias="verificationLog")
    # [V2.7] New scoring and origin fields
    quality_score: int = Field(default=0, alias="qualityScore")
    query_origin: Optional[str] = Field(None, alias="queryOrigin")
    language_of_result: Optional[str] = Field(None, alias="languageOfResult")
    
    passes_constraints: bool = Field(default=False, alias="passesConstraints")
    wool_percentage: Optional[str] = Field(None, alias="woolPercentage")
    made_to_measure: bool = Field(default=False, alias="madeToMeasure")
    
    # [V2.1] Chain Detection
    is_chain: bool = Field(default=False, alias="isChain")
    
    # Extended company information
    revenue: Optional[str] = None
    clothing_types: Optional[List[str]] = Field(default_factory=list, alias="clothingTypes")
    target_gender: Optional[str] = Field(None, alias="targetGender")
    brand_style: Optional[str] = Field(None, alias="brandStyle")
    business_model: Optional[str] = Field(None, alias="businessModel")
    company_overview: Optional[str] = Field(None, alias="companyOverview")
    
    # Location quality (premium street detection)
    location_quality: Optional[str] = Field(default="unknown", alias="locationQuality")
    # Values: "premium", "standard", "unknown"
    location_score: int = Field(default=0, alias="locationScore")
    # Score: 0-10 based on street tier
    
    # [V2.5] New fields for utility
    store_locations: Optional[List[str]] = Field(default_factory=list, alias="storeLocations")
    detailed_description: Optional[str] = Field(None, alias="detailedDescription")
    
    # [V2.6] Contact Information
    contact_name: Optional[str] = Field(None, alias="contactName")
    contact_role: Optional[str] = Field(None, alias="contactRole")
    contact_email: Optional[str] = Field(None, alias="contactEmail")
    contact_phone: Optional[str] = Field(None, alias="contactPhone")
    
    # [V3.1] Headquarters information
    headquarters_address: Optional[str] = Field(None, alias="headquartersAddress")
    
    # Compatibility field for DB/Frontend mismatch
    avg_suit_price_eur: Optional[float] = Field(default=None)
    fit_score: int = Field(default=0, alias="fitScore")
    price_note: Optional[str] = Field(default=None, alias="priceNote")
    material_composition: Optional[List[str]] = Field(default_factory=list, alias="materialComposition")
    price_source: Optional[str] = Field(default=None, alias="priceSource")

    @field_validator('verification_log', 'clothing_types', 'store_locations', 'material_composition', mode='before')
    @classmethod
    def parse_json_fields(cls, v):
        if isinstance(v, str):
            import json
            try:
                # Try to parse as JSON if it's a string
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
            except:
                pass
            import ast
            try:
                parsed = ast.literal_eval(v)
                if isinstance(parsed, list):
                    return parsed
            except:
                pass
            # Fallback for plain strings
            if v.strip():
                if v.startswith('[') and v.endswith(']'):
                    # Trying to strip brackets and split
                    content = v[1:-1].strip()
                    if content:
                        return [s.strip(" '\"") for s in content.split(',')]
                    return []
                return [v]
            return []
        return v

    @property
    def price_display(self) -> str:
        if self.avg_suit_price_eur is not None and self.avg_suit_price_eur > 0:
            return f"€{self.avg_suit_price_eur:.0f}"
        return f"${self.average_suit_price_usd:.0f}"

    def model_post_init(self, __context):
        # Ensure we have a price for the logic
        if (self.average_suit_price_usd == 0 or self.average_suit_price_usd is None) and self.avg_suit_price_eur is not None:
            self.average_suit_price_usd = self.avg_suit_price_eur * 1.08  # Approx conversion
        if self.avg_suit_price_eur is None and self.average_suit_price_usd is not None and self.average_suit_price_usd > 0:
            self.avg_suit_price_eur = self.average_suit_price_usd / 1.08



class EmailLog(BaseModel):
    """Log entry for email sending"""
    brand_name: str
    timestamp: str
    status: str  # "success" or "failed"
    error: Optional[str] = None


class QuerySearchResults(BaseModel):
    """Search results grouped by query"""
    query_index: int
    query: str
    query_origin: Optional[str] = None
    results: List[Dict[str, str]] = Field(default_factory=list)


class ProspectorState(BaseModel):
    """State for the prospecting agent workflow"""
    target_city: str
    target_country: str = "USA"
    tier: int = 2 # 1=Global Metro, 2=Regional
    search_queries: List[str] = Field(default_factory=list)
    query_origins: List[str] = Field(default_factory=list) # To track axis/source
    candidate_urls: List[str] = Field(default_factory=list)
    potential_brands: List[BrandLead] = Field(default_factory=list)
    verified_brands: List[BrandLead] = Field(default_factory=list)
    search_results: List[QuerySearchResults] = Field(default_factory=list)
    approval_status: Dict[str, bool] = Field(default_factory=dict)
    email_logs: List[EmailLog] = Field(default_factory=list)
    exchange_rate: float = 1.08
    price_threshold_eur: float = 500
    price_threshold_usd: float = 540
    max_stores: int = 20
    progress: List[str] = Field(default_factory=list)
    error: Optional[str] = None
    cached: bool = False
    cached_count: int = 0
    queries_approved: bool = False
    brands_approved: bool = False
    force_refresh: bool = False



class SearchRequest(BaseModel):
    """Request body for prospect search"""
    city: str
    force_refresh: bool = Field(default=False, description="Force new search even if city has cached results")


class ApprovalRequest(BaseModel):
    """Request body for email approval"""
    model_config = ConfigDict(populate_by_name=True)
    
    brand_name: str = Field(alias="brandName")
    brand_data: Dict[str, Any] = Field(alias="brandData")


class ProgressMessage(BaseModel):
    """SSE progress message"""
    type: str  # "progress", "complete", "error"
    message: Optional[str] = None
    timestamp: str
    verified_brands: Optional[List[BrandLead]] = None
    exchange_rate: Optional[float] = None
    price_threshold_usd: Optional[float] = None





class SelectedCandidate(BaseModel):
    """A candidate selected by the selection agent"""
    query_index: int
    url: str
    title: str
    reason: str


class ExtractedContent(BaseModel):
    """Content extracted from a URL"""
    url: str
    content: Optional[str] = None
    # V3 fields for enhanced matching pipeline
    quality_score: int = 0                          # Multi-language keyword score
    query_origin: Optional[str] = None              # Which search axis found this
    language_detected: Optional[str] = None         # ISO 639-1 (e.g., "en", "it", "fr")
    price_confidence: float = 0.0                   # 0.0-1.0 confidence in price extraction
    extraction_method: Optional[str] = None         # "tavily", "jina", "smart_nav", "crawl4ai"
    # [V4] Structured data from Crawl4AI pipeline
    structured_data: Optional[Dict[str, Any]] = None
class WorkflowResumeRequest(BaseModel):
    """Request body to resume a paused agent workflow"""
    thread_id: str
    action: str  # "approve", "reject", "edit"
    node: str    # "discovery", "persistence"
    data: Optional[Dict] = None  # e.g., {"queries": ["q1", "q2"]}
