"""08a Part 2 — Phase 1 reports keep their numbers after the move to cycles.

A fixed fixture: bugs in two Releases sent back from review and from Done
(before release QA ships), plus a merge into a Done bug. The expected numbers
below were captured from the Phase 1 implementation (``regression_history``,
``is_regression``, ``regression_count``) before the reports were ported to
``issue_cycles`` — see docs/phase-2/08a-release-stream-cycles.md Part 2.

The ported reports read cycles with ``start_reason in (review, release_qa)``
of bugs in ``kind = release`` containers, so the same fixture plus cycles in
the Stream and task cycles must not move any number.
"""

from types import SimpleNamespace

import pytest

from app.services.regression_service import regression_service


async def _bug(factories, release_id, *, priority, labels):
    bug = await factories.issue(release_id=release_id, labels=labels)
    resp = await factories.admin_client.post(f"/issues/{bug.id}/triage", json={
        "outcome": "accept", "priority": priority, "release_id": release_id,
    })
    assert resp.status_code == 200, resp.text
    return bug


async def _assign(factories, item, dev):
    resp = await factories.admin_client.patch(f"/issues/{item.id}", json={"assignee_id": dev.id})
    assert resp.status_code == 200, resp.text


class Flow:
    """Drives items through the fixture. Sending work back is the one step
    whose API changes between Phase 1 and v3 (the regression action → reject
    and returns), so it lives here."""

    def __init__(self, factories, dev_client, qa_client):
        self.admin = factories.admin_client
        self.dev = dev_client
        self.qa = qa_client

    async def deliver(self, item):
        status = (await self.admin.get(f"/issues/{item.id}")).json()["status"]
        if status != "in_progress":
            resp = await self.dev.post(f"/issues/{item.id}/transition", json={"to": "in_progress"})
            assert resp.status_code == 200, resp.text
        resp = await self.dev.post(f"/issues/{item.id}/fix", json={"mr_url": None})
        assert resp.status_code == 200, resp.text

    async def verify(self, item):
        resp = await self.admin.post(f"/issues/{item.id}/verify", json={"outcome": "pass"})
        assert resp.status_code == 200 and resp.json()["status"] == "done", resp.text

    async def back_from_review(self, item):
        resp = await self.qa.post(f"/issues/{item.id}/regression")
        assert resp.status_code == 200, resp.text

    async def back_from_done(self, item):
        resp = await self.qa.post(f"/issues/{item.id}/regression")
        assert resp.status_code == 200, resp.text


async def _fixture(factories, client_for):
    dev = await factories.user(role="developer")
    qa = await factories.user(role="qa")
    project = await factories.project()
    r1 = await factories.release(project_id=project.id, version="9.1.0")
    r2 = await factories.release(project_id=project.id, version="9.2.0")
    flow = Flow(factories, await client_for(dev), await client_for(qa))

    # A — rejected once in review, then verified.
    a = await _bug(factories, r1.id, priority="high", labels=["ui"])
    await _assign(factories, a, dev)
    await flow.deliver(a)
    await flow.back_from_review(a)
    await flow.deliver(a)
    await flow.verify(a)

    # B — chronic: back from Done once, rejected twice in review.
    b = await _bug(factories, r1.id, priority="critical", labels=["ui", "api"])
    await _assign(factories, b, dev)
    await flow.deliver(b)
    await flow.verify(b)
    await flow.back_from_done(b)
    for _ in range(2):
        await flow.deliver(b)
        await flow.back_from_review(b)
    await flow.deliver(b)
    await flow.verify(b)

    # C — first-pass fix, no returns.
    c = await _bug(factories, r2.id, priority="medium", labels=["api"])
    await _assign(factories, c, dev)
    await flow.deliver(c)
    await flow.verify(c)

    # F — Done in R2, then a new report is merged into it (merge return).
    f = await _bug(factories, r2.id, priority="low", labels=["db"])
    await _assign(factories, f, dev)
    await flow.deliver(f)
    await flow.verify(f)
    report = await factories.issue(release_id=r2.id)
    resp = await factories.admin_client.post(f"/issues/{report.id}/triage", json={
        "outcome": "duplicate", "duplicate_of_id": f.id,
    })
    assert resp.status_code == 200, resp.text

    return SimpleNamespace(
        dev=dev, qa=qa, project=project, r1=r1, r2=r2, flow=flow,
        a=a, b=b, c=c, f=f, admin_id=factories.admin_id,
    )


async def _numbers(factories, fx, db_session):
    admin = factories.admin_client
    r1 = (await admin.get(f"/reports/releases/{fx.r1.id}")).json()
    r2 = (await admin.get(f"/reports/releases/{fx.r2.id}")).json()
    reg = (await admin.get("/reports/regressions", params={"project_id": fx.project.id})).json()
    metrics = (await admin.get(
        "/reports/contributions/metrics", params={"project_id": fx.project.id},
    )).json()
    fragility = await regression_service.get_component_fragility(db_session, fx.project.id)
    await db_session.rollback()

    keys = {fx.a.id: "A", fx.b.id: "B", fx.c.id: "C", fx.f.id: "F"}
    numbers_by_key = {}
    for item in (fx.a, fx.b, fx.c, fx.f):
        numbers_by_key[item.issue_number] = keys[item.id]
    users = {fx.dev.id: "dev", fx.qa.id: "qa", fx.admin_id: "admin"}

    return {
        "release_regression_count": {"r1": r1["regression_count"], "r2": r2["regression_count"]},
        "global_rate": reg["globalRegressionRate"],
        "chronic": reg["chronicRegressionCount"],
        "most_fragile": reg["mostFragileComponent"],
        "rate_by_release": {r["release"]: r["rate"] for r in reg["regressionRateByRelease"]},
        "priority_by_release": reg["priorityByRelease"],
        "label_rates": reg["labelRegressionRates"],
        "detectors": sorted(
            (users[d["user"]["id"]], d["detected"]) for d in reg["topDetectors"]
        ),
        "rework_regressions": sorted(
            (users[d["user"]["id"]], d["regressionCount"]) for d in reg["reworkByDeveloper"]
        ),
        "top_issues": sorted(
            (numbers_by_key[i["id"]], i["regressions"]) for i in reg["topRegressionIssues"]
        ),
        "metrics_rate": metrics["summary"]["regression_rate"],
        "fragility": sorted(
            (e["label"], e["regression_count"], e["affected_issues"]) for e in fragility
        ),
    }


#: Captured from the Phase 1 implementation (2026-09-30), before the port.
PHASE1_NUMBERS = {
    "release_regression_count": {"r1": 2, "r2": 1},
    "global_rate": 100.0,
    "chronic": 1,
    "most_fragile": "ui",
    "rate_by_release": {"9.2.0": 100.0, "9.1.0": 100.0},
    "priority_by_release": [
        {"release": "9.2.0", "critical": 0, "high": 0, "medium": 0, "low": 1},
        {"release": "9.1.0", "critical": 1, "high": 1, "medium": 0, "low": 0},
    ],
    "label_rates": [
        {"release": "9.2.0", "ui": 0.0, "api": 0.0, "db": 33.3},
        {"release": "9.1.0", "ui": 100.0, "api": 50.0, "db": 0.0},
    ],
    "detectors": [("admin", 1), ("qa", 4)],
    "rework_regressions": [("dev", 5)],
    "top_issues": [("A", 1), ("B", 3), ("F", 1)],
    "metrics_rate": 60.0,
    "fragility": [("api", 3, 1), ("db", 1, 1), ("ui", 4, 2)],
}


@pytest.mark.asyncio
async def test_phase1_report_numbers_for_fixed_fixture(factories, client_for, db_session):
    fx = await _fixture(factories, client_for)
    assert await _numbers(factories, fx, db_session) == PHASE1_NUMBERS


@pytest.mark.asyncio
async def test_stream_and_task_cycles_do_not_change_phase1_reports(
    factories, client_for, db_session,
):
    fx = await _fixture(factories, client_for)
    stream_id = await factories.stream_id(project_id=fx.project.id)

    # D — a bug in the Stream, back from production and rejected in review.
    d = await _bug(factories, stream_id, priority="critical", labels=["ui"])
    await _assign(factories, d, fx.dev)
    await fx.flow.deliver(d)
    await fx.flow.verify(d)
    await fx.flow.back_from_done(d)
    await fx.flow.deliver(d)
    await fx.flow.back_from_review(d)

    # E — a task in R1 rejected in review, twice.
    e = await factories.issue(
        project_id=fx.project.id, type="task", release_id=fx.r1.id, labels=["ui"],
    )
    await _assign(factories, e, fx.dev)
    for _ in range(2):
        await fx.flow.deliver(e)
        await fx.flow.back_from_review(e)

    assert [c["start_reason"] for c in await factories.cycles(d.id)] == [
        "planned", "production", "review",
    ]
    assert [c["start_reason"] for c in await factories.cycles(e.id)] == [
        "planned", "review", "review",
    ]

    numbers = await _numbers(factories, fx, db_session)
    # The extra items are in the metrics' denominator (items filed in the
    # period), exactly as they would have been in Phase 1 — never in the numerator.
    # Label rates divide by the release's item count, so the task in 9.1.0
    # lowers them the same way (2 of 3 items carry "ui", 1 of 3 "api").
    expected = {
        **PHASE1_NUMBERS,
        "metrics_rate": round(3 / 7 * 100, 1),
        "label_rates": [
            {"release": "9.2.0", "ui": 0.0, "api": 0.0, "db": 33.3},
            {"release": "9.1.0", "ui": 66.7, "api": 33.3, "db": 0.0},
        ],
    }
    assert numbers == expected
