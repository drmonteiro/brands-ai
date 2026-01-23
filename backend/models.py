"""
Pydantic models for the Confeções Lança prospector
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from enum import Enum


class BrandLead(BaseModel):
    """Schema for a discovered brand lead"""
    name: str
    website_url: str
    store_count: int = Field(ge=0, default=1)  # 0 means unknown, will be treated as 1
    average_suit_price_usd: float = Field(ge=0, default=0)
    city: Optional[str] = None
    origin_country: str = "USA"
    verified: bool = False
    verification_log: List[str] = Field(default_factory=list)
    passes_constraints: bool = False
    
    # Extended company information
    revenue: Optional[str] = None
    clothing_types: List[str] = Field(default_factory=list)
    target_gender: Optional[str] = None
    brand_style: Optional[str] = None
    business_model: Optional[str] = None
    company_overview: Optional[str] = None


class EmailLog(BaseModel):
    """Log entry for email sending"""
    brand_name: str
    timestamp: str
    status: str  # "success" or "failed"
    error: Optional[str] = None


class ProspectorState(BaseModel):
    """State for the prospecting agent workflow"""
    target_city: str
    target_country: str = "USA"
    search_queries: List[str] = Field(default_factory=list)
    candidate_urls: List[str] = Field(default_factory=list)
    potential_brands: List[BrandLead] = Field(default_factory=list)
    verified_brands: List[BrandLead] = Field(default_factory=list)
    approval_status: Dict[str, bool] = Field(default_factory=dict)
    email_logs: List[EmailLog] = Field(default_factory=list)
    exchange_rate: float = 1.08
    price_threshold_eur: float = 500
    price_threshold_usd: float = 540
    max_stores: int = 20
    progress: List[str] = Field(default_factory=list)
    error: Optional[str] = None


class SearchRequest(BaseModel):
    """Request body for prospect search"""
    city: str


class ApprovalRequest(BaseModel):
    """Request body for email approval"""
    brand_name: str
    brand_data: BrandLead


class ProgressMessage(BaseModel):
    """SSE progress message"""
    type: str  # "progress", "complete", "error"
    message: Optional[str] = None
    timestamp: str
    verified_brands: Optional[List[BrandLead]] = None
    exchange_rate: Optional[float] = None
    price_threshold_usd: Optional[float] = None


class QuerySearchResults(BaseModel):
    """Search results grouped by query"""
    query_index: int
    query: str
    results: List[Dict[str, str]] = Field(default_factory=list)


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
