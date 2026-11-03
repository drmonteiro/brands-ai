"""LinkedIn drafts, the draft endpoint, and the status/notes fixes."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from models import BrandLead
from routers import linkedin as linkedin_router
from routers import prospects as prospects_router
from services import database as db
from services import linkedin_outreach as lo


def _brand(**kw):
    return BrandLead(name=kw.pop("name", "Cad & The Dandy"), website_url="https://x.test", **kw)


def _llm(monkeypatch, content=None, error=None):
    llm = MagicMock()
    llm.ainvoke = AsyncMock(
        side_effect=error, return_value=SimpleNamespace(content=content)
    )
    monkeypatch.setattr(lo, "_drafting_llm", lambda: llm)


CONTACT = {"name": "James Sleater", "role": "Owner", "linkedin_url": "https://linkedin.com/in/james"}


async def test_uses_llm_drafts_when_valid(monkeypatch):
    _llm(monkeypatch, json.dumps({"connection_note": "Hi James", "message": "Longer"}))
    out = await lo.generate_linkedin_drafts(_brand(), CONTACT)
    assert out == {"connection_note": "Hi James", "message": "Longer"}


async def test_oversized_llm_note_is_replaced_not_cut(monkeypatch):
    _llm(monkeypatch, json.dumps({"connection_note": "x" * 201, "message": "Longer"}))
    out = await lo.generate_linkedin_drafts(_brand(), CONTACT)
    assert "x" * 50 not in out["connection_note"]
    assert out["connection_note"].startswith("Hello James")
    assert out["message"] == "Longer"


async def test_llm_failure_falls_back_to_template(monkeypatch):
    _llm(monkeypatch, error=RuntimeError("down"))
    out = await lo.generate_linkedin_drafts(_brand(), CONTACT)
    assert "1973" in out["connection_note"]
    assert "15-minute" in out["message"]


async def test_invalid_json_falls_back_to_template(monkeypatch):
    _llm(monkeypatch, "not json")
    out = await lo.generate_linkedin_drafts(_brand(), CONTACT)
    assert "1973" in out["connection_note"]


def test_fallback_note_respects_limit_with_very_long_brand():
    out = lo.fallback_drafts(_brand(name="B" * 400), CONTACT)
    assert len(out["connection_note"]) <= lo.CONNECTION_NOTE_MAX_CHARS
    assert "1973" in out["connection_note"]


def test_fallback_does_not_greet_a_brand_named_profile():
    out = lo.fallback_drafts(_brand(), {"name": "cad and the dandy"})
    assert out["connection_note"].startswith("Hello,")


def _client(router):
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_draft_endpoint_returns_normalized_profile(monkeypatch):
    monkeypatch.setattr(linkedin_router, "generate_linkedin_drafts",
                        AsyncMock(return_value={"connection_note": "n", "message": "m"}))
    res = _client(linkedin_router.router).post("/api/linkedin/draft", json={
        "brandData": {"name": "Brand Co", "website_url": "https://x.test", "city": "london",
                      "linkedin_contacts": json.dumps([CONTACT]), "linkedin_contacts_checked_at": "2026-11-03T10:00:00+00:00"},
        "contact": CONTACT,
    })
    assert res.status_code == 200
    body = res.json()
    assert body["profile_url"] == "https://www.linkedin.com/in/james"
    assert body["search_url"].endswith("keywords=Brand%20Co%20london")


def test_draft_endpoint_never_returns_a_non_linkedin_url(monkeypatch):
    monkeypatch.setattr(linkedin_router, "generate_linkedin_drafts",
                        AsyncMock(return_value={"connection_note": "n", "message": "m"}))
    res = _client(linkedin_router.router).post("/api/linkedin/draft", json={
        "brandData": {"name": "Brand Co", "website_url": "https://x.test"},
        "contact": {"name": "X", "linkedin_url": "https://evil.example/in/x"},
    })
    assert res.json()["profile_url"] is None


def _db_pool(monkeypatch, command_tag):
    conn = MagicMock()
    conn.execute = AsyncMock(return_value=command_tag)
    acquire = MagicMock()
    acquire.__aenter__ = AsyncMock(return_value=conn)
    acquire.__aexit__ = AsyncMock(return_value=False)
    pool = MagicMock()
    pool.acquire.return_value = acquire
    monkeypatch.setattr(db.PostgresManager, "get_pool", AsyncMock(return_value=pool))
    return conn


async def test_status_update_reports_found_and_keeps_notes(monkeypatch):
    conn = _db_pool(monkeypatch, "UPDATE 1")
    assert await db.update_prospect_status("id", "contacted") is True
    assert "COALESCE($2, notes)" in conn.execute.await_args.args[0]


async def test_status_update_reports_missing_prospect(monkeypatch):
    _db_pool(monkeypatch, "UPDATE 0")
    assert await db.update_prospect_status("nope", "contacted") is False


def test_status_route_succeeds_when_prospect_exists(monkeypatch):
    _db_pool(monkeypatch, "UPDATE 1")
    res = _client(prospects_router.router).patch("/api/prospects/abc/status", json={"status": "contacted"})
    assert res.status_code == 200


def test_lookup_route_saves_contacts(monkeypatch):
    contacts = [{"name": "A", "role": "CEO", "tier": 1, "linkedin_url": "https://www.linkedin.com/in/a", "evidence": ""}]
    prospect = {"id": "abc", "name": "B", "website_url": "https://b.test"}
    monkeypatch.setenv("EXA_API_KEY", "k")
    monkeypatch.setattr(prospects_router, "get_prospect_by_id", AsyncMock(return_value=prospect))
    monkeypatch.setattr(prospects_router, "find_linkedin_contacts", AsyncMock(return_value=(contacts, True)))
    save = AsyncMock(return_value=True)
    facts = AsyncMock(return_value=1)
    monkeypatch.setattr(prospects_router, "update_prospect_linkedin_contacts", save)
    monkeypatch.setattr(prospects_router, "save_brand_linkedin_contacts", facts)
    res = _client(prospects_router.router).post("/api/prospects/abc/linkedin-contacts")
    assert res.status_code == 200
    save.assert_awaited_once_with("abc", contacts)
    assert facts.await_args.args[0][0]["contact_linkedin"].endswith("/in/a")


def test_lookup_route_reports_failure_without_marking_checked(monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "k")
    monkeypatch.setattr(prospects_router, "get_prospect_by_id", AsyncMock(return_value={"name": "B"}))
    monkeypatch.setattr(prospects_router, "find_linkedin_contacts", AsyncMock(return_value=([], False)))
    save = AsyncMock()
    monkeypatch.setattr(prospects_router, "update_prospect_linkedin_contacts", save)
    res = _client(prospects_router.router).post("/api/prospects/abc/linkedin-contacts")
    assert res.status_code == 502
    save.assert_not_awaited()
