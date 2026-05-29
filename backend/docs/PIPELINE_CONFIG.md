# Pipeline configuration

Production workflow: **4 LangGraph nodes** — `discovery` → `filter` → `enrich` → `score_save`.

Search and enrichment use **Exa** (`EXA_API_KEY`). Runtime ranking weights live in `services/runtime_scoring.py`.

## Concurrency and batch sizes

| Variable | Default | Where used | Meaning |
|----------|---------|------------|---------|
| `EXA_QUERY_MAX_CONCURRENT` | `6` (clamped 5–8) | `discovery.py` | Parallel Exa queries per city |
| `EXA_NUM_RESULTS` | `20` | `discovery.py` | Results per Exa query |
| `EXA_MAX_RETRIES` | `3` | `discovery.py` | Retries on transient Exa errors |
| `EXA_RETRY_INITIAL_SEC` | `1.5` | `discovery.py` | Exponential backoff base |
| `EXA_MAX_CONCURRENT` | `5` (code constant) | `enrich.py`, `location_enrichment.py` | Parallel Exa fetches during enrich |
| `ENRICH_LLM_BATCH_CONCURRENT` | `0` (= sequential) | `enrich.py` | Parallel LLM enrich batches; `0` disables cap |
| `FIT_LLM_BATCH_CONCURRENT` | `0` | `persistence.py` | Parallel fit-assessment batches |
| `ENRICH_BATCH_SIZE` | `6` (code) | `enrich.py` | Brands per enrich LLM batch |
| `FIT_BATCH_SIZE` | `8` (code) | `persistence.py` | Brands per fit LLM batch |
| `FILTER_BATCH_SIZE` | `12` (code) | `filter.py` | Candidates per filter LLM call |
| `FILTER_CONTENT_EXCERPT_CHARS` | `3500` (code) | `filter.py` | Snippet length sent to filter LLM |
| `HQ_LLM_MAX_CONCURRENT` | `3` (code) | `location_enrichment.py` | Parallel HQ location LLM calls |

Set env vars in `backend/.env` (see `backend/.env.example`).

## Required API keys

- `AZURE_OPENAI_*` — LLM + embeddings
- `EXA_API_KEY` — discovery and supplemental enrich search
- `POSTGRES_*` / `SYNC_DATABASE_URL` — persistence + pgvector

## Optional

- `GOOGLE_PLACES_API_KEY` — store/HQ location enrichment
- `BRAND_FACTS_TTL_DAYS` — cross-city brand cache TTL (default 30)
- `EUR_USD_RATE`, `GBP_TO_EUR`, etc. — FX for prompts/UI

## Scoring (runtime)

Weights in `services/runtime_scoring.py`: `WEIGHT_SIMILARITY`, `WEIGHT_LLM_FIT`, `WEIGHT_PRICE`, `WEIGHT_SIZE`.

Offline rubric evaluation: `rubric.yaml` + `evaluation/rubric_evaluator.py` (not used in the live pipeline).
