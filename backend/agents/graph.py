"""
LangGraph Orchestration for Confeções Lança Prospecting Workflow
"""

import operator
import contextlib
import asyncio
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
    force_refresh: bool


# ============================================================================
# GRAPH DEFINITION
# ============================================================================

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool
from config import Config

# ============================================================================
# CHECKPOINTER SETUP
# ============================================================================

# Shared connection pool for the checkpointer
_graph_pool = None
_setup_done = False
_setup_lock = asyncio.Lock()

async def get_graph_pool():
    global _graph_pool
    if _graph_pool is None:
        DB_URI = Config.SYNC_DATABASE_URL or "postgresql://lanca:lanca_password@localhost:5432/lanca_leads"
        # Neon pooler (port 5432 with -pooler) works best without complex channel binding
        # and with a small pool size for internal tools
        connection_kwargs = {
            "autocommit": True,
            "prepare_threshold": 0,
        }
        _graph_pool = AsyncConnectionPool(
            conninfo=DB_URI, 
            max_size=10, 
            min_size=1,
            kwargs=connection_kwargs,
            open=True
        )
    return _graph_pool

@contextlib.asynccontextmanager
async def _get_app_with_postgres():
    global _setup_done
    pool = await get_graph_pool()
    checkpointer = AsyncPostgresSaver(pool)
    
    # Ensure setup is only called once successfully
    async with _setup_lock:
        if not _setup_done:
            try:
                await checkpointer.setup()
                _setup_done = True
                print("[GRAPH] Checkpointer setup complete.")
            except Exception as e:
                print(f"[GRAPH] Checkpointer setup failed: {e}")
                # Don't set _setup_done to True so it can retry
                raise
    
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
    
    app = workflow.compile(checkpointer=checkpointer)
    yield app

# Helper to execute against checking
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
# (Original version at the top is the one we use)
