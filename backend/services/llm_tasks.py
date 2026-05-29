"""
Per-task LLM deployment selection (gpt-5.1 deep vs gpt-5-mini fast).

Override via env: LLM_<TASK>_FAST=true|false
  e.g. LLM_STRUCTURED_EXTRACT_FAST=false  → force 5.1 for unified enrich extraction
       LLM_FIT_ASSESSMENT_FAST=false     → default; keep fit on 5.1

If structured extraction on mini degrades price quality, set LLM_STRUCTURED_EXTRACT_FAST=false.
"""

import os
from typing import Dict

# True → AZURE_OPENAI_DEPLOYMENT_FAST (gpt-5-mini); False → gpt-5.1
TASK_USE_FAST_DEFAULT: Dict[str, bool] = {
    "structured_extract": True,
    "hq_batch": True,
    "hq_from_content": True,
    "store_extract": True,
    "fit_assessment": False,
    "discovery": True,
    "filter": True,
    "city_context": True,
}


def task_uses_fast_model(task: str) -> bool:
    """Whether this pipeline task should use the fast (mini) deployment."""
    env_key = f"LLM_{task.upper()}_FAST"
    raw = os.getenv(env_key)
    if raw is not None:
        return raw.strip().lower() in ("1", "true", "yes", "on")
    return TASK_USE_FAST_DEFAULT.get(task, True)
