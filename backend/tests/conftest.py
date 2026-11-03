"""Shared fixtures."""

from unittest.mock import AsyncMock

import pytest


@pytest.fixture(autouse=True)
def _no_real_linkedin_lookup(monkeypatch):
    """config.py loads .env, so without this enrich tests would call Exa for real."""
    monkeypatch.setattr(
        "agents.nodes.persistence.attach_linkedin_contacts",
        AsyncMock(return_value=0),
    )
    monkeypatch.setattr(
        "agents.nodes.persistence.save_brand_linkedin_contacts",
        AsyncMock(return_value=0),
    )
    # Tests don't have a database, and these only record why brands were rejected.
    monkeypatch.setattr("agents.nodes.persistence.save_lead_rejections", AsyncMock())
    monkeypatch.setattr("agents.nodes.filter.save_lead_rejections", AsyncMock())
