"""Per-task LLM deployment selection."""

import os

from services.llm_tasks import task_uses_fast_model


def test_fit_assessment_defaults_to_deep():
    os.environ.pop("LLM_FIT_ASSESSMENT_FAST", None)
    assert task_uses_fast_model("fit_assessment") is False


def test_structured_extract_defaults_to_fast():
    os.environ.pop("LLM_STRUCTURED_EXTRACT_FAST", None)
    assert task_uses_fast_model("structured_extract") is True


def test_env_override_forces_deep_extract(monkeypatch):
    monkeypatch.setenv("LLM_STRUCTURED_EXTRACT_FAST", "false")
    assert task_uses_fast_model("structured_extract") is False
