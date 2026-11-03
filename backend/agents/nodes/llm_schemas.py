"""Validated shapes for LLM answers. One malformed item is dropped, not the whole batch."""

import logging
from typing import Any, List, Literal, Optional, Type, TypeVar

from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger("node.llm_schemas")

T = TypeVar("T", bound=BaseModel)


class FilterVerdict(BaseModel):
    i: int
    keep: bool
    brand_name: str = ""
    reason: str = ""


class FitAssessment(BaseModel):
    i: int
    fit_score: float = Field(ge=0, le=10)
    level: Literal["same", "above", "below", "different_category"]
    closest_client: Optional[str] = None
    fit_reason: str = ""


def validate_items(model: Type[T], rows: Any) -> List[T]:
    items: List[T] = []
    for row in rows if isinstance(rows, list) else [rows]:
        try:
            items.append(model.model_validate(row))
        except ValidationError as e:
            logger.warning("Dropping invalid %s: %s", model.__name__, e.errors()[:1])
    return items
