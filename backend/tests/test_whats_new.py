"""What's new (TASK-575): notes shown once per person, per team.

The API tests run against notes built here (``get_notes`` overridden), dated
around today so the new-account rule — a note published no later than the day
someone joined counts as seen — is exercised with real ``created_at`` values.
The shipped notes are checked separately: they parse, and every tour anchor
exists in the frontend.
"""

import re
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
import pytest_asyncio

from app.main import app as fastapi_app
from app.whats_new.notes import NOTES_DIR, Note, get_notes, load_notes, parse_note

TODAY = datetime.now(UTC).date()
TOMORROW = TODAY + timedelta(days=1)
LATER = TODAY + timedelta(days=2)


def _step(anchor: str = "sidebar-toggle", **kw) -> dict:
    return {"anchor": anchor, "title": "Collapse it", "body": "Click here.", **kw}


def _feature(teams: list[str], title: str, **kw) -> dict:
    return {"kind": "new", "teams": teams, "icon": "sparkles", "title": title,
            "body": "It does a thing.", "tour": [_step()], **kw}


def _fix(teams: list[str], title: str) -> dict:
    return {"kind": "fixed", "teams": teams, "title": title}


def _note(day: date, highlights: list[dict], teams: tuple[str, ...] = ("tech", "support")) -> Note:
    used = {t for h in highlights for t in h["teams"]}
    headline = {t: {"title": f"{t} {day}", "summary": f"For {t}."} for t in teams if t in used}
    return Note.model_validate(
        {"id": day.isoformat(), "date": day, "headline": headline, "highlights": highlights}
    )


@pytest.fixture
def notes():
    """Install notes for the API; newest first, like ``load_notes``."""
    installed: list[Note] = []

    def install(*items: Note) -> None:
        installed[:] = sorted(items, key=lambda n: n.date, reverse=True)

    fastapi_app.dependency_overrides[get_notes] = lambda: tuple(installed)
    yield install
    fastapi_app.dependency_overrides.pop(get_notes, None)


@pytest_asyncio.fixture
async def people(factories, client_for):
    dev = await factories.user(role="developer")
    admin = await factories.user(role="admin")
    support = await factories.user(role="support")
    return {
        "dev": await client_for(dev),
        "admin": await client_for(admin),
        "support": await client_for(support),
    }


async def whats_new(client) -> dict:
    resp = await client.get("/whats-new")
    assert resp.status_code == 200, resp.text
    return resp.json()


# ── Per team ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_each_team_sees_only_its_highlights_and_headline(people, notes):
    notes(_note(TOMORROW, [
        _feature(["tech", "support"], "Collapse the sidebar"),
        _feature(["tech"], "Keep going after you create"),
        _feature(["support"], "Reports remember your template"),
        _fix(["tech"], "Board drag no longer jumps."),
    ]))

    for who in ("dev", "admin"):  # admin is on the tech team
        body = await whats_new(people[who])
        [note] = body["notes"]
        assert note["title"] == f"tech {TOMORROW}"
        assert [h["title"] for h in note["highlights"]] == [
            "Collapse the sidebar", "Keep going after you create", "Board drag no longer jumps.",
        ]

    [note] = (await whats_new(people["support"]))["notes"]
    assert note["title"] == f"support {TOMORROW}"
    assert [h["title"] for h in note["highlights"]] == [
        "Collapse the sidebar", "Reports remember your template",
    ]
    assert note["highlights"][0]["tour"] == [
        {"anchor": "sidebar-toggle", "title": "Collapse it", "body": "Click here.",
         "advance": "next", "route": None},
    ]


@pytest.mark.asyncio
async def test_a_note_with_nothing_for_a_team_is_left_out_of_its_changelog(people, notes):
    notes(
        _note(LATER, [_feature(["tech"], "Tech only")]),
        _note(TOMORROW, [_feature(["support"], "Support only")]),
    )
    assert [n["id"] for n in (await whats_new(people["dev"]))["notes"]] == [LATER.isoformat()]
    support = await whats_new(people["support"])
    assert [n["id"] for n in support["notes"]] == [TOMORROW.isoformat()]
    # The newest note *for Support* is the one that opens for them.
    assert support["show"] == TOMORROW.isoformat()


# ── Shown once ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_the_newest_unseen_note_opens_once_and_seeing_it_twice_is_harmless(people, notes):
    notes(_note(LATER, [_feature(["tech"], "Newest")]), _note(TOMORROW, [_feature(["tech"], "Older")]))
    dev = people["dev"]

    body = await whats_new(dev)
    assert body["show"] == LATER.isoformat()
    assert [n["seen"] for n in body["notes"]] == [False, False]

    for _ in range(2):
        resp = await dev.post("/whats-new/seen", json={"note_ids": [LATER.isoformat()]})
        assert resp.status_code == 204, resp.text
    body = await whats_new(dev)
    assert body["show"] is None
    assert [n["seen"] for n in body["notes"]] == [True, False]

    # Opening the changelog records every unseen note at once.
    resp = await dev.post("/whats-new/seen", json={"note_ids": [LATER.isoformat(), TOMORROW.isoformat()]})
    assert resp.status_code == 204
    assert [n["seen"] for n in (await whats_new(dev))["notes"]] == [True, True]


@pytest.mark.asyncio
async def test_one_persons_seen_state_never_reaches_another(people, notes):
    notes(_note(TOMORROW, [_feature(["tech", "support"], "Shared")]))
    await people["dev"].post("/whats-new/seen", json={"note_ids": [TOMORROW.isoformat()]})
    assert (await whats_new(people["dev"]))["show"] is None
    assert (await whats_new(people["admin"]))["show"] == TOMORROW.isoformat()
    assert (await whats_new(people["support"]))["show"] == TOMORROW.isoformat()


@pytest.mark.asyncio
async def test_a_fixes_only_note_waits_in_the_changelog(people, notes):
    notes(_note(TOMORROW, [_fix(["tech"], "Board drag no longer jumps.")]))
    body = await whats_new(people["dev"])
    assert body["show"] is None
    assert body["notes"][0]["seen"] is False


@pytest.mark.asyncio
async def test_a_note_published_before_someone_joined_counts_as_seen(people, notes):
    # The people were created today: today's and yesterday's notes predate
    # them (or arrived with them), tomorrow's doesn't.
    notes(
        _note(TOMORROW, [_feature(["tech"], "After they joined")]),
        _note(TODAY, [_feature(["tech"], "The day they joined")]),
        _note(TODAY - timedelta(days=1), [_feature(["tech"], "Before they joined")]),
    )
    body = await whats_new(people["dev"])
    assert [n["seen"] for n in body["notes"]] == [False, True, True]
    assert body["show"] == TOMORROW.isoformat()

    notes(_note(TODAY, [_feature(["tech"], "The day they joined")]))
    assert (await whats_new(people["dev"]))["show"] is None


@pytest.mark.asyncio
async def test_marking_an_unknown_note_is_refused(people, notes):
    notes(_note(TOMORROW, [_feature(["tech"], "Real")]))
    resp = await people["dev"].post("/whats-new/seen", json={"note_ids": ["1999-01-01"]})
    assert resp.status_code == 404
    assert resp.json()["code"] == "note_not_found"


# ── The note files ────────────────────────────────────────────────────────────

_FRONTEND_SRC = next(
    (p for p in (Path(__file__).resolve().parents[2] / "frontend" / "src", Path("/frontend-src")) if p.is_dir()),
    None,
)


def test_every_shipped_note_parses():
    shipped = load_notes(NOTES_DIR)
    assert shipped, "no notes in app/whats_new/notes"
    assert len({n.id for n in shipped}) == len(shipped)


@pytest.mark.skipif(
    _FRONTEND_SRC is None,
    reason="frontend/src isn't reachable: run from the repo, or with docker-compose.dev.yml's /frontend-src mount",
)
def test_every_tour_anchor_exists_in_the_frontend():
    code = "\n".join(p.read_text(encoding="utf-8") for p in _FRONTEND_SRC.rglob("*.jsx"))
    found = set(re.findall(r"""data-tour=["']([a-z0-9-]+)["']""", code))
    for note in load_notes(NOTES_DIR):
        missing = note.anchors() - found
        assert not missing, f"{note.id}.md points at anchors no element carries: {sorted(missing)}"


def _write(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


_GOOD = """---
date: 2026-10-24
headline:
  tech: {title: T, summary: S}
highlights:
  - kind: fixed
    teams: [tech]
    title: A fix.
---
"""


@pytest.mark.parametrize(
    ("name", "text", "message"),
    [
        ("2026-10-25.md", _GOOD, "file name must be the note's date"),
        ("2026-10-24.md", _GOOD + "\nA body after the front matter.\n", "nothing after it"),
        ("2026-10-24.md", _GOOD.replace("teams: [tech]", "teams: [tech, support]"), "no headline for support"),
        ("2026-10-24.md", _GOOD.replace("title: A fix.", "title: A fix.\n    icon: bug"), "title only"),
        ("2026-10-24.md", _GOOD.replace("kind: fixed", "kind: new"), "needs an icon, a body and a tour"),
        ("2026-10-24.md", _GOOD.replace("teams: [tech]", "teams: [everyone]"), "teams"),
    ],
)
def test_a_malformed_note_is_refused(tmp_path, name, text, message):
    with pytest.raises(ValueError, match=message):
        parse_note(_write(tmp_path, name, text))


def test_tour_copy_stays_short(tmp_path):
    base = _GOOD.replace(
        "  - kind: fixed\n    teams: [tech]\n    title: A fix.\n",
        "  - kind: new\n    teams: [tech]\n    icon: sparkles\n    title: Thing\n    body: Does it.\n"
        "    tour:\n      - anchor: sidebar-toggle\n        title: TITLE\n        body: BODY\n",
    )

    def note(title: str, body: str) -> Path:
        return _write(tmp_path, "2026-10-24.md", base.replace("TITLE", title).replace("BODY", body))

    parse_note(note("Five words is the limit", "Fifteen words " * 7 + "ok"))
    with pytest.raises(ValueError, match="at most 5 words"):
        parse_note(note("Six words is over the limit", "Fine."))
    with pytest.raises(ValueError, match="at most 15 words"):
        parse_note(note("Fine", "word " * 16))

