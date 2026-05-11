"""Logs de duração legíveis por passo do pipeline de prospecção."""

from __future__ import annotations

import logging
import time
from typing import Any


def format_duration(seconds: float) -> str:
    if seconds < 0:
        seconds = 0.0
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    rest = seconds - (minutes * 60)
    if minutes > 0 and rest < 10:
        return f"{minutes}m {rest:.1f}s"
    if minutes > 0:
        return f"{minutes}m {rest:.0f}s"
    return f"{seconds:.1f}s"


def step_begin(
    logger: logging.Logger,
    step_id: str,
    city: str,
    description: str,
) -> float:
    logger.info(
        "[PIPELINE] ▶ INÍCIO | step=%s | cidade=%s | %s",
        step_id,
        city,
        description,
    )
    return time.perf_counter()


def step_end(
    logger: logging.Logger,
    step_id: str,
    city: str,
    t0: float,
    summary: str = "",
    **metrics: Any,
) -> float:
    elapsed = time.perf_counter() - t0
    tail = ""
    if metrics:
        parts = [f"{k}={v}" for k, v in metrics.items() if v is not None]
        if parts:
            tail = " | " + " | ".join(parts)
    sum_part = f" | resultado: {summary}" if summary else ""
    logger.info(
        "[PIPELINE] ✓ FIM    | step=%s | cidade=%s | duração=%s (%.2f min)%s%s",
        step_id,
        city,
        format_duration(elapsed),
        elapsed / 60.0,
        sum_part,
        tail,
    )
    return elapsed
