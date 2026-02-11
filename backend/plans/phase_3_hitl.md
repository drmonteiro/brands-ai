# Phase 3 Implementation Plan: Human-in-the-Loop (HITL)

Objective: Incorporate manual approval steps in the LangGraph prospecting workflow to allow users to review and refine the AI's search and selection process.

## Architecture Change
- Use LangGraph Breakpoints (`interrupt_before` or `interrupt_after`).
- Add nodes specifically for waiting for approval.
- Implement an API endpoint to "resume" the graph with user input.

## Checklist

### 1. Refactor Graph for Interrupts
- [ ] Add `query_approval` field to `GraphState`.
- [ ] Add `brand_approval` field to `GraphState`.
- [ ] Update `create_prospector_graph` to include breakpoints before `discovery` (Query approval).

### 2. Manual Approval Nodes
- [ ] Implement `human_review_queries` node.
- [ ] Implement `human_review_brands` node.

### 3. Backend API for Resuming
- [ ] Create `@app.post("/api/workflow/resume")` endpoint.
- [ ] Support passing approved queries and brands back into the state.

### 4. Frontend Integration
- [ ] Create UI components for query review.
- [ ] Implement real-time updates when the graph is waiting.
