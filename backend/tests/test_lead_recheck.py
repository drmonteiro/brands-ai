"""Regenerating a city must clean it up without losing sales work or punishing outages."""

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from services import lead_recheck as lr
from services import prospect_jobs as jobs


def _old(id_="a", status="new", name="Brand", url="https://b.test"):
    return {"id": id_, "name": name, "website_url": url, "country": "UK", "status": status, "store_count": 2}


def _assessed(accepted=True, code=None, reason="", **fields):
    return {"_gate": {"accepted": accepted, "code": code, "reason": reason}, "final_score": 80, "llm_fit_score": 8, **fields}


@pytest.fixture
def store(monkeypatch):
    update, hide, reject = AsyncMock(), AsyncMock(), AsyncMock()
    monkeypatch.setattr(lr, "update_lead_after_recheck", update)
    monkeypatch.setattr(lr, "hide_lead", hide)
    monkeypatch.setattr(lr, "save_lead_rejections", reject)
    return update, hide, reject


def _assess_returns(monkeypatch, *assessed):
    monkeypatch.setattr(lr, "assess_brands", AsyncMock(return_value=list(assessed)))


async def test_passing_lead_is_updated(monkeypatch, store):
    update, hide, _ = store
    _assess_returns(monkeypatch, _assessed())
    summary = await lr.recheck_city_leads("London", [_old()])
    update.assert_awaited_once()
    hide.assert_not_awaited()
    assert summary["updated"] == 1


async def test_failing_lead_is_hidden_with_its_reason_recorded(monkeypatch, store):
    _, hide, reject = store
    _assess_returns(monkeypatch, _assessed(False, "not_suit_brand", "Jeans"))
    summary = await lr.recheck_city_leads("London", [_old()])
    hide.assert_awaited_once_with("a")
    assert reject.await_args.args[1][0]["code"] == "not_suit_brand"
    assert reject.await_args.args[1][0]["stage"] == "regeneration"
    assert summary["hidden"] == 1


@pytest.mark.parametrize("status", ["contacted", "converted"])
async def test_leads_with_sales_work_are_never_hidden(monkeypatch, store, status):
    update, hide, _ = store
    _assess_returns(monkeypatch, _assessed(False, "not_suit_brand", "Jeans"))
    summary = await lr.recheck_city_leads("London", [_old(status=status)])
    hide.assert_not_awaited()
    update.assert_not_awaited()
    assert summary["kept_sales_work"] == 1


@pytest.mark.parametrize("code", ["extraction_failed", "similarity_failed", "level_unknown"])
async def test_technical_failures_do_not_hide_a_lead(monkeypatch, store, code):
    update, hide, _ = store
    _assess_returns(monkeypatch, _assessed(False, code, "x"))
    summary = await lr.recheck_city_leads("London", [_old()])
    hide.assert_not_awaited()
    update.assert_not_awaited()
    assert summary["unverified"] == 1


async def test_outage_during_assessment_changes_nothing(monkeypatch, store):
    update, hide, _ = store
    monkeypatch.setattr(lr, "assess_brands", AsyncMock(side_effect=RuntimeError("Azure down")))
    summary = await lr.recheck_city_leads("London", [_old(), _old("b")])
    hide.assert_not_awaited()
    update.assert_not_awaited()
    assert summary["unverified"] == 2


async def test_existing_client_is_hidden_without_spending_on_assessment(monkeypatch, store):
    _, hide, _ = store
    assess = AsyncMock()
    monkeypatch.setattr(lr, "assess_brands", assess)
    summary = await lr.recheck_city_leads("Madrid", [_old(name="GARCÍA MADRID")])
    assess.assert_not_awaited()
    hide.assert_awaited_once_with("a")
    assert summary["hidden"] == 1


async def test_large_cities_are_checked_in_batches(monkeypatch, store):
    assess = AsyncMock(side_effect=lambda rows: [_assessed() for _ in rows])
    monkeypatch.setattr(lr, "assess_brands", assess)
    leads = [_old(str(i)) for i in range(lr.RECHECK_BATCH_SIZE + 1)]
    assert (await lr.recheck_city_leads("London", leads))["updated"] == len(leads)
    assert assess.await_count == 2


def test_update_fields_clear_an_unproven_old_price():
    fields = lr.fields_from_assessment(_assessed(price_status="unconfirmed"))
    assert fields["avg_suit_price_eur"] == 0
    assert fields["price_note"] is None
    assert fields["price_status"] == "unconfirmed"


def test_update_fields_build_a_range_from_proven_prices():
    fields = lr.fields_from_assessment(_assessed(
        price_status="confirmed", avg_suit_price_eur=1000, price_range_min_eur=800, price_range_max_eur=1200,
    ))
    assert fields["price_note"] == "€800 - €1200"
    assert fields["avg_suit_price_eur"] == 1000


async def test_regenerate_rechecks_only_leads_from_before_the_search(monkeypatch):
    old = [_old()]
    monkeypatch.setattr(jobs, "get_active_leads_for_city", AsyncMock(return_value=old))
    recheck = AsyncMock(return_value={"added": 0, "updated": 1, "hidden": 0, "kept_sales_work": 0, "unverified": 0})
    monkeypatch.setattr(jobs, "recheck_city_leads", recheck)
    monkeypatch.setattr(jobs, "_execute_pipeline", AsyncMock(side_effect=_complete))
    job = jobs.ProspectJob(city="London", force_refresh=True, regenerate=True)
    await jobs._run_job(job)
    recheck.assert_awaited_once_with("London", old)
    assert job.summary["added"] == 3
    assert job.status == jobs.JobStatus.COMPLETED


async def _complete(job, keep_running=False):
    job.brand_count = 3


async def test_failed_search_leaves_existing_leads_untouched(monkeypatch):
    monkeypatch.setattr(jobs, "get_active_leads_for_city", AsyncMock(return_value=[_old()]))
    recheck = AsyncMock()
    monkeypatch.setattr(jobs, "recheck_city_leads", recheck)

    async def _fail(job, keep_running=False):
        job.status = jobs.JobStatus.FAILED

    monkeypatch.setattr(jobs, "_execute_pipeline", _fail)
    job = jobs.ProspectJob(city="London", force_refresh=True, regenerate=True)
    await jobs._run_job(job)
    recheck.assert_not_awaited()


def test_regenerate_route_starts_a_job(monkeypatch):
    from routers import cities

    start = AsyncMock(return_value={"city": "london", "status": "running"})
    monkeypatch.setattr(cities, "start_prospect_job", start)
    app = FastAPI()
    app.include_router(cities.router)
    res = TestClient(app).post("/api/cities/london/regenerate")
    assert res.status_code == 200
    start.assert_awaited_once_with("london", force_refresh=True, regenerate=True)
