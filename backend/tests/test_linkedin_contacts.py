"""LinkedIn contact lookup: search, verification rules, ranking, failure handling."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from services import linkedin_contacts as lc


def _result(slug, text="profile text", title="t"):
    return SimpleNamespace(url=f"https://linkedin.com/in/{slug}", title=title, text=text)


def _exa(people=(), domain=()):
    exa = MagicMock()

    def search(query, **kwargs):
        rows = people if kwargs.get("category") == "people" else domain
        if isinstance(rows, Exception):
            raise rows
        return SimpleNamespace(results=list(rows))

    exa.search.side_effect = search
    return exa


def _llm_returns(monkeypatch, rows):
    llm = MagicMock()
    llm.ainvoke = AsyncMock(return_value=SimpleNamespace(content=json.dumps(rows)))
    monkeypatch.setattr(lc, "_verification_llm", lambda: llm)
    return llm


BRAND = {"name": "Cad & The Dandy", "website_url": "https://cadandthedandy.co.uk", "origin_country": "UK"}


def _row(i, name, role="Owner", tier=1, current=True):
    return {"i": i, "name": name, "role": role, "tier": tier, "current": current, "evidence": "x"}


async def test_ranks_by_tier_and_caps_at_three(monkeypatch):
    exa = _exa(people=[_result(s) for s in "abcd"])
    _llm_returns(monkeypatch, [
        _row(1, "Store Lead", "Store Manager", 3),
        _row(2, "Buyer One", "Head of Buying", 2),
        _row(3, "Owner One", "Owner", 1),
        _row(4, "Buyer Two", "Head of Product", 2),
    ])
    contacts, ok = await lc.find_linkedin_contacts(exa, BRAND)
    assert ok is True
    assert [c["name"] for c in contacts] == ["Owner One", "Buyer One", "Buyer Two"]


async def test_rejects_former_staff_and_excluded_roles(monkeypatch):
    exa = _exa(people=[_result("a"), _result("b"), _result("c")])
    _llm_returns(monkeypatch, [
        _row(1, "Former Owner", current=False),
        _row(2, "Sales Assistant", "Sales Assistant", 0),
        _row(3, "Real Owner"),
    ])
    contacts, _ = await lc.find_linkedin_contacts(exa, BRAND)
    assert [c["name"] for c in contacts] == ["Real Owner"]


async def test_url_comes_from_search_results_never_from_llm(monkeypatch):
    exa = _exa(people=[_result("real-person")])
    row = _row(1, "Real Person")
    row["linkedin_url"] = "https://linkedin.com/in/invented"
    _llm_returns(monkeypatch, [row, _row(99, "Invented Index")])
    contacts, _ = await lc.find_linkedin_contacts(exa, BRAND)
    assert [c["linkedin_url"] for c in contacts] == ["https://www.linkedin.com/in/real-person"]


async def test_merges_both_searches_and_dedupes_same_profile(monkeypatch):
    exa = _exa(
        people=[_result("same"), SimpleNamespace(url="https://uk.linkedin.com/company/x", title="", text="")],
        domain=[SimpleNamespace(url="https://www.linkedin.com/in/same/", title="", text="dup"), _result("other")],
    )
    llm = _llm_returns(monkeypatch, [_row(1, "Same"), _row(2, "Other")])
    contacts, _ = await lc.find_linkedin_contacts(exa, BRAND)
    assert len(contacts) == 2
    prompt = llm.ainvoke.await_args.args[0]
    assert "/company/" not in prompt
    assert exa.search.call_count == 2


async def test_brand_named_profile_ranks_below_real_people(monkeypatch):
    exa = _exa(people=[_result("brand"), _result("person")])
    _llm_returns(monkeypatch, [
        _row(1, "cad & the dandy", "Owner", 1),
        _row(2, "Store Lead", "Store Manager", 3),
    ])
    contacts, _ = await lc.find_linkedin_contacts(exa, BRAND)
    assert [c["name"] for c in contacts] == ["Store Lead", "cad & the dandy"]


async def test_brand_named_profile_kept_when_only_route(monkeypatch):
    exa = _exa(people=[_result("brand")])
    _llm_returns(monkeypatch, [_row(1, "CAD AND THE DANDY", "Owner", 1)])
    contacts, ok = await lc.find_linkedin_contacts(exa, BRAND)
    assert ok is True and len(contacts) == 1


async def test_site_found_profile_is_offered_to_verification(monkeypatch):
    exa = _exa()
    brand = {**BRAND, "contact_linkedin": "https://linkedin.com/in/site-owner",
             "contact_name": "Site Owner", "contact_role": "Founder"}
    llm = _llm_returns(monkeypatch, [_row(1, "Site Owner", "Founder")])
    contacts, _ = await lc.find_linkedin_contacts(exa, brand)
    assert contacts[0]["linkedin_url"] == "https://www.linkedin.com/in/site-owner"
    assert "brand's own website" in llm.ainvoke.await_args.args[0]


async def test_exa_failure_returns_empty_and_not_ok(monkeypatch):
    exa = _exa(people=RuntimeError("boom"), domain=RuntimeError("boom"))
    _llm_returns(monkeypatch, [])
    contacts, ok = await lc.find_linkedin_contacts(exa, BRAND)
    assert contacts == [] and ok is False


async def test_partial_exa_failure_keeps_results_but_not_ok(monkeypatch):
    exa = _exa(people=[_result("a")], domain=RuntimeError("boom"))
    _llm_returns(monkeypatch, [_row(1, "Owner One")])
    contacts, ok = await lc.find_linkedin_contacts(exa, BRAND)
    assert len(contacts) == 1 and ok is False


async def test_llm_failure_returns_empty_and_not_ok(monkeypatch):
    exa = _exa(people=[_result("a")])
    llm = MagicMock()
    llm.ainvoke = AsyncMock(side_effect=RuntimeError("down"))
    monkeypatch.setattr(lc, "_verification_llm", lambda: llm)
    assert await lc.find_linkedin_contacts(exa, BRAND) == ([], False)


async def test_no_candidates_is_a_successful_empty_lookup(monkeypatch):
    llm = _llm_returns(monkeypatch, [])
    assert await lc.find_linkedin_contacts(_exa(), BRAND) == ([], True)
    llm.ainvoke.assert_not_awaited()


def test_apply_contacts_sets_primary_fields():
    brand = {"contact_name": "Old", "contact_linkedin": "https://linkedin.com/company/x", "contact_email": "a@b.c"}
    contacts = [{"name": "New", "role": "CEO", "tier": 1, "linkedin_url": "https://www.linkedin.com/in/new", "evidence": ""}]
    lc.apply_contacts_to_brand(brand, contacts)
    assert brand["contact_name"] == "New"
    assert brand["contact_role"] == "CEO"
    assert brand["contact_linkedin"].endswith("/in/new")
    assert brand["contact_email"] == "a@b.c"


def test_apply_empty_contacts_keeps_existing_primary():
    brand = {"contact_name": "Old", "contact_linkedin": "https://linkedin.com/company/x"}
    lc.apply_contacts_to_brand(brand, [])
    assert brand["contact_name"] == "Old"
    assert brand["contact_linkedin"].endswith("/company/x")


@pytest.mark.parametrize("url,expected", [
    ("linkedin.com/in/abc/", "https://www.linkedin.com/in/abc"),
    ("https://uk.linkedin.com/in/abc?trk=x", "https://www.linkedin.com/in/abc"),
    ("https://linkedin.com/in/joakim-sv%C3%A4rdh-0a", "https://www.linkedin.com/in/joakim-sv%C3%A4rdh-0a"),
    ("https://linkedin.com/company/abc", None),
    ("https://evil.example/linkedin.com/in/abc", None),
    ("javascript:alert(1)//linkedin.com/in/abc", None),
    ("", None),
    (None, None),
])
def test_normalize_profile_url(url, expected):
    assert lc.normalize_profile_url(url) == expected


async def test_attach_skips_brands_checked_recently(monkeypatch):
    from datetime import datetime, timezone
    monkeypatch.setenv("EXA_API_KEY", "k")
    find = AsyncMock(return_value=([], True))
    monkeypatch.setattr(lc, "find_linkedin_contacts", find)
    monkeypatch.setattr(lc, "Exa", MagicMock())
    fresh = {"name": "Fresh", "linkedin_contacts": [{"name": "Kept"}],
             "linkedin_contacts_checked_at": datetime.now(timezone.utc)}
    stale = {"name": "Never", "linkedin_contacts_checked_at": None}
    assert await lc.attach_linkedin_contacts([fresh, stale]) == 1
    assert find.await_count == 1
    assert fresh["linkedin_contacts"] == [{"name": "Kept"}]
    assert stale["linkedin_contacts_checked_at"] is not None


async def test_attach_failed_lookup_leaves_brand_unchecked(monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "k")
    monkeypatch.setattr(lc, "find_linkedin_contacts", AsyncMock(return_value=([], False)))
    monkeypatch.setattr(lc, "Exa", MagicMock())
    brand = {"name": "B"}
    await lc.attach_linkedin_contacts([brand])
    assert brand.get("linkedin_contacts_checked_at") is None


async def test_attach_never_raises_when_lookup_blows_up(monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "k")
    monkeypatch.setattr(lc, "find_linkedin_contacts", AsyncMock(side_effect=RuntimeError("x")))
    monkeypatch.setattr(lc, "Exa", MagicMock())
    brand = {"name": "B"}
    assert await lc.attach_linkedin_contacts([brand]) == 0


async def test_attach_without_exa_key_is_a_noop(monkeypatch):
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    assert await lc.attach_linkedin_contacts([{"name": "B"}]) == 0


@pytest.mark.parametrize("module", ["routers", "services.linkedin_contacts", "agents.nodes.enrich", "services.linkedin_outreach"])
def test_imports_cleanly_as_first_import(module):
    """In-process tests hide circular imports: startup order is what counts."""
    import subprocess
    import sys

    result = subprocess.run([sys.executable, "-c", f"import {module}"], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr[-800:]
