"""
LangGraph Orchestration for Confeções Lança Prospecting Workflow
"""

import operator
from typing import Annotated, List, Dict, Any, Union, Optional
from typing_extensions import TypedDict

from langgraph.graph import StateGraph, END


from models import BrandLead, ProspectorState, QuerySearchResults
from .nodes.initializer import initialize_search
from .nodes.discovery import discovery_node
from .nodes.validator import validation_node
from .nodes.persistence import filter_node

# ============================================================================
# WORKFLOW STATE DEFINITION
# ============================================================================

class GraphState(TypedDict):
    """
    State of the prospecting workflow.
    Uses Annotated with operator.add for fields that should accumulate results.
    """
    target_city: str
    target_country: str
    search_queries: List[str]
    candidate_urls: Annotated[List[str], operator.add]
    potential_brands: Annotated[List[BrandLead], operator.add]
    verified_brands: Annotated[List[BrandLead], operator.add]
    search_results: List[QuerySearchResults]  # To replace global mutable list
    progress: Annotated[List[str], operator.add]
    exchange_rate: float
    price_threshold_eur: float
    price_threshold_usd: float
    max_stores: int
    error: Optional[str]
    cached: bool
    cached_count: int
    queries_approved: bool
    brands_approved: bool


# ============================================================================
# GRAPH DEFINITION
# ============================================================================

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool
from config import Config

# ============================================================================
# CHECKPOINTER SETUP
# ============================================================================

# Connection string for PostgresSaver (needs to be sync for the pool normally, 
# but PostgresSaver can take a pool)
# We use the SYNC_DATABASE_URL for the psycopg pool
DB_URI = Config.SYNC_DATABASE_URL or "postgresql://lanca:lanca_password@localhost:5432/lanca_leads"



# Helper to execute against checking
# Using a slightly different approach for the wrapper to handle the pool/checkpointer lifecycle
async def run_prospector_workflow(initial_state_data: Dict[str, Any], thread_id: str = None):
    """
    High-level entry point to run the prospector graph.
    """
    if not thread_id:
        thread_id = "prospect_search_" + initial_state_data.get("target_city", "unknown")
        
    config = {"configurable": {"thread_id": thread_id}}
    
    # Use ConnectionPool to get the app
    async with _get_app_with_postgres() as app:
        state = await app.aget_state(config)
        
        if not state.values:
            result = await app.ainvoke(initial_state_data, config=config)
        else:
            result = await app.ainvoke(None, config=config)
            
        final_state = await app.aget_state(config)
        next_node = final_state.next
        is_interrupted = len(next_node) > 0
        
        return final_state.values, is_interrupted, next_node[0] if is_interrupted else None

# Private helper to manage graph+checkpointer lifecycle
import contextlib

@contextlib.asynccontextmanager
async def _get_app_with_postgres():
    connection_kwargs = {
        "autocommit": True,
        "prepare_threshold": 0,
    }
    
    # Use AsyncConnectionPool for async compatibility
    async with AsyncConnectionPool(conninfo=DB_URI, max_size=20, kwargs=connection_kwargs) as pool:
        checkpointer = AsyncPostgresSaver(pool)
        
        # setup() must be awaited for AsyncPostgresSaver
        await checkpointer.setup()
        
        workflow = StateGraph(GraphState)
        workflow.add_node("initialize", initialize_search)
        workflow.add_node("discovery", discovery_node)
        workflow.add_node("validation", validation_node)
        workflow.add_node("persistence", filter_node)
        
        workflow.set_entry_point("initialize")
        workflow.add_conditional_edges("initialize", lambda x: "end" if x.get("cached") else "discovery", {"end": END, "discovery": "discovery"})
        workflow.add_edge("discovery", "validation")
        workflow.add_edge("validation", "persistence")
        workflow.add_edge("persistence", END)
        
        app = workflow.compile(checkpointer=checkpointer, interrupt_before=["discovery", "persistence"])
        yield app
