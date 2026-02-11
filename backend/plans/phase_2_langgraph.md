# Phase 2: LangGraph Orchestration Layer - Implementation Plan

## Objective
Migrate the linear prospecting workflow to a stateful, agentic graph using LangGraph. This enables complex decision-making, better error recovery, and Human-in-the-Loop (HITL) manual approval.

## Architecture
The workflow will be divided into discrete nodes:
1.  **Search Node**: Generates optimized queries and retrieves initial candidates from Tavily.
2.  **Selection Node**: Filter and select the best URLs for deep scraping.
3.  **Scraping Node**: Uses Firecrawl/Crawl4AI to extract deep information (price, stores, materials).
4.  **Analysis Node**: Compares with Lança's 18 clients (PostgreSQL vector search) and calculates scores.
5.  **Deduplication Node**: Ensures no duplicates across cities/domains in PostgreSQL.
6.  **Human Approval Node**: (HITL) Pauses execution for manual review before saving/emailing.

## Checklist

### 1. Foundation
- [ ] Install LangGraph and prebuilt dependencies.
- [ ] Define `WorkflowState` (extending `ProspectorState`).
- [ ] Create `backend/agents/graph.py` with the graph definition.

### 2. Implementation - Nodes
- [ ] Implement `search_node`.
- [ ] Implement `selection_node`.
- [ ] Implement `scraping_node` (Integration with Firecrawl).
- [ ] Implement `analysis_node`.
- [ ] Implement `persistence_node` (Save to PostgreSQL).

### 3. Implementation - Router & Logic
- [ ] Define conditional edges (e.g., "should_scrape", "needs_approval").
- [ ] Implement checkpointing with PostgreSQL (LangGraph Checkpointer).

### 4. Integration
- [ ] Update `backend/main.py` to use the new LangGraph workflow.
- [ ] Update frontend to support SSE updates from the graph.

## Current Progress
- [x] Phase 1 - Migration to PostgreSQL complete.
- [ ] Phase 2 - Started LangGraph design.
