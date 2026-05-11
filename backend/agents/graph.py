"""
LangGraph Orchestration for Confeções Lança Prospecting Workflow

Simplified 4-node pipeline:
  Discovery → Filter → Enrich → Score+Save
"""

import operator
import contextlib
import asyncio
import logging
from typing import Annotated, List, Dict, Any, Optional
from typing_extensions import TypedDict

from langgraph.graph import StateGraph, END
from models import BrandLead

logger = logging.getLogger("graph")

from .nodes.discovery import discovery_node
from .nodes.filter import filter_node
from .nodes.enrich import enrich_node
from .nodes.persistence import score_and_save_node


# ============================================================================
# WORKFLOW STATE
# ============================================================================

def _replace_list(existing: Optional[List[Any]], new: Optional[List[Any]]) -> List[Any]:
    """Replace (not concatenate) lists — avoids checkpoint duplication."""
    if new is not None:
        return list(new)
    return existing or []


class GraphState(TypedDict):
    # Core
    target_city: str
    target_country: str
    exchange_rate: float

    # Node 1 → Node 2: raw Exa results
    search_results_raw: Annotated[List[Dict], _replace_list]

    # Node 2 → Node 3: filtered brands (only men's suits)
    filtered_brands: Annotated[List[Dict], _replace_list]

    # Node 3 → Node 4: enriched brands (structured data + Places)
    enriched_brands: Annotated[List[Dict], _replace_list]

    # Node 4 output: final verified brands
    verified_brands: Annotated[List[BrandLead], _replace_list]

    # SSE progress messages (appended across nodes)
    progress: Annotated[List[str], operator.add]

    # Error tracking
    error: Optional[str]


# ============================================================================
# CHECKPOINTER (PostgreSQL)
# ============================================================================

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool
from config import Config

_graph_pool = None
_setup_done = False
_setup_lock = asyncio.Lock()


async def get_graph_pool():
    global _graph_pool
    if _graph_pool is None:
        DB_URI = Config.SYNC_DATABASE_URL or "postgresql://lanca:lanca_password@localhost:5432/lanca_leads"
        connection_kwargs = {
            "autocommit": True,
            "prepare_threshold": 0,
            "keepalives": 1,
            "keepalives_idle": 30,
            "keepalives_interval": 10,
            "keepalives_count": 5,
        }
        _graph_pool = AsyncConnectionPool(
            conninfo=DB_URI,
            max_size=10,
            min_size=1,
            timeout=120.0,
            max_lifetime=1800.0,
            max_idle=600.0,
            reconnect_timeout=300.0,
            kwargs=connection_kwargs,
            open=False,
            check=AsyncConnectionPool.check_connection,
        )
        await _graph_pool.open(wait=True, timeout=120.0)
    return _graph_pool


@contextlib.asynccontextmanager
async def _get_app_with_postgres():
    global _setup_done
    pool = await get_graph_pool()
    checkpointer = AsyncPostgresSaver(pool)

    async with _setup_lock:
        if not _setup_done:
            try:
                await checkpointer.setup()
                _setup_done = True
                logger.info("Postgres checkpointer setup complete")
            except Exception as e:
                logger.error("Checkpointer setup failed: %s", e)
                raise

    logger.info("Building graph: discovery → filter → enrich → score_save")
    workflow = StateGraph(GraphState)
    workflow.add_node("discovery", discovery_node)
    workflow.add_node("filter", filter_node)
    workflow.add_node("enrich", enrich_node)
    workflow.add_node("score_save", score_and_save_node)

    workflow.set_entry_point("discovery")
    workflow.add_edge("discovery", "filter")
    workflow.add_edge("filter", "enrich")
    workflow.add_edge("enrich", "score_save")
    workflow.add_edge("score_save", END)

    app = workflow.compile(checkpointer=checkpointer)
    logger.info("Graph compiled — ready to stream")
    yield app


async def run_prospector_workflow(initial_state_data: Dict[str, Any], thread_id: str = None):
    """High-level entry point to run the prospector graph."""
    if not thread_id:
        thread_id = "prospect_search_" + initial_state_data.get("target_city", "unknown")

    config = {"configurable": {"thread_id": thread_id}}

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
