"""Slice 12 — the pure search-text rules (``app/search/normalize.py``,
``documents.py``, ``comment_rules.py``).

Behaviour is proven end to end through ``GET /search`` in
``test_search_engine.py``; these pin down the text rules without a database
or an embedding model.
"""

from types import SimpleNamespace

from app.search.comment_rules import RULE_DROPPED, RULE_KEPT, rule_label
from app.search.documents import CHUNK_CHARS, build_documents, curl_paths
from app.search.normalize import fold, normalize, strip_markdown

ZWNJ = "\u200c"


# ── normalize ────────────────────────────────────────────────────────────────


def test_arabic_letters_become_persian():
    assert normalize("كتاب علي") == "کتاب علی"
    assert normalize("مدرسة") == "مدرسه"


def test_persian_and_arabic_digits_become_ascii():
    assert normalize("خطای ۴۱۳ و ٥٠٠") == "خطای 413 و 500"


def test_diacritics_tatweel_and_direction_marks_are_removed():
    assert normalize("س\u064eلام") == "سلام"
    assert normalize("ســـلام") == "سلام"
    assert normalize("\u200fسلام\u200e\u200d") == "سلام"


def test_repeated_zwnj_collapses_and_whitespace_trims():
    assert normalize(f"  ری{ZWNJ}{ZWNJ}اکشن   ها \n") == f"ری{ZWNJ}اکشن ها"


def test_zwnj_next_to_a_space_is_dropped():
    assert normalize(f"پیام{ZWNJ} ها") == "پیام ها"


def test_normalize_keeps_case_and_latin_text():
    assert normalize("Group Chat") == "Group Chat"


def test_normalize_is_idempotent():
    s = f"ري{ZWNJ}{ZWNJ}اكشن ۱۲"
    assert normalize(normalize(s)) == normalize(s)


# ── fold (keyword index only) ────────────────────────────────────────────────


def test_fold_removes_zwnj_folds_alef_madda_and_lowercases():
    assert fold(f"ری{ZWNJ}اکشن") == "ریاکشن"
    assert fold("آموزش") == "اموزش"
    assert fold("Group CHAT") == "group chat"


def test_missing_half_space_and_written_half_space_fold_the_same():
    assert fold(f"ثبت{ZWNJ}نام زبان{ZWNJ}آموز") == "ثبتنام زباناموز"
    assert fold(f"ثبت{ZWNJ}نام") == fold("ثبتنام")


# ── markdown ─────────────────────────────────────────────────────────────────


def test_markdown_links_become_their_text():
    assert strip_markdown("see [the doc](https://x.io/a)") == "see the doc"


def test_code_blocks_inline_code_and_mentions_are_removed():
    text = "before\n```\nTraceback: boom\n```\nrun `npm ci` @sara please"
    out = strip_markdown(text)
    assert "Traceback" not in out
    assert "npm ci" not in out
    assert "@sara" not in out and "sara" not in out
    assert "before" in out and "please" in out


def test_emphasis_and_heading_markers_are_removed_but_snake_case_survives():
    assert strip_markdown("## **Bold** title with group_chat") == "Bold title with group_chat"


# ── documents ────────────────────────────────────────────────────────────────


def _item(**kw):
    base = dict(
        title="Reactions vanish",
        description=None,
        reproduction_steps=None,
        curl_command=None,
        labels=[],
    )
    return SimpleNamespace(**{**base, **kw})


def _comment(id_, body, is_internal=False):
    return SimpleNamespace(id=id_, body=body, is_internal=is_internal)


def test_body_joins_title_description_and_steps_without_field_labels():
    item = _item(
        description="Open a **group** chat",
        reproduction_steps=[
            {
                "description": "React to a message",
                "expected_result": "kept",
                "actual_result": "gone",
            },
        ],
    )
    docs = build_documents(item, [], {})
    assert docs.title == "Reactions vanish"
    assert len(docs.body_chunks) == 1
    body = docs.body_chunks[0]
    for part in ("Reactions vanish", "Open a group chat", "React to a message", "kept", "gone"):
        assert part in body
    for label in ("Title", "Description", "Expected", "Actual", "Step", "**"):
        assert label not in body


def test_long_body_is_chunked_with_overlap():
    words = [f"w{i}" for i in range(2000)]
    docs = build_documents(_item(description=" ".join(words)), [], {})
    assert len(docs.body_chunks) > 1
    assert all(len(c) <= CHUNK_CHARS for c in docs.body_chunks)
    first_tail = docs.body_chunks[0].split()[-5:]
    assert all(w in docs.body_chunks[1] for w in first_tail)
    # Every word lands in some chunk — nothing is truncated away.
    joined = " ".join(docs.body_chunks)
    assert "w0" in joined and "w1999" in joined


def test_short_body_is_one_chunk():
    docs = build_documents(_item(description="x " * 100), [], {})
    assert len(docs.body_chunks) == 1


def test_curl_keeps_url_paths_only():
    curl = (
        "curl -X POST 'https://api.example.com/api/v1/chat/reactions?token=abc' "
        "-H 'Authorization: Bearer s3cr3t' -d '{\"emoji\":\"x\"}'"
    )
    assert curl_paths(curl) == ["/api/v1/chat/reactions"]
    docs = build_documents(_item(curl_command=curl), [], {})
    assert "/api/v1/chat/reactions" in docs.keyword_text
    for secret in ("s3cr3t", "token", "abc", "authorization", "example.com", "emoji"):
        assert secret not in docs.keyword_text


def test_keyword_text_is_folded_and_carries_labels_and_inline_code():
    item = _item(
        title="ری‌اکشن ذخیره نمی‌شود",
        description="calls `/api/v1/chat/reactions` and gets 413",
        labels=["Chat"],
    )
    docs = build_documents(item, [], {})
    assert "ریاکشن" in docs.keyword_text
    assert "/api/v1/chat/reactions" in docs.keyword_text
    assert "413" in docs.keyword_text
    assert "chat" in docs.keyword_text
    assert docs.keyword_text == docs.keyword_text.lower()


def test_talk_holds_only_comments_the_rule_kept():
    comments = [
        _comment(1, "The reaction id is null in the group payload, see the logs"),
        _comment(2, "ok"),
        _comment(3, "Internal: the bug is in the fan-out worker for groups", is_internal=True),
        _comment(4, "Never classified yet, but long enough to matter here"),
    ]
    labels = {1: RULE_KEPT, 2: RULE_DROPPED, 3: RULE_KEPT}
    docs = build_documents(_item(), comments, labels)
    assert [(t.timeline_id, t.is_internal) for t in docs.talk] == [(1, False), (3, True)]
    assert "payload" in docs.talk[0].text


def test_comments_never_reach_body_or_keyword_text():
    comments = [_comment(1, "a distinctive phrase zebracorn in a comment body")]
    docs = build_documents(_item(), comments, {1: RULE_KEPT})
    assert "zebracorn" not in " ".join(docs.body_chunks)
    assert "zebracorn" not in docs.keyword_text


# ── comment rule ─────────────────────────────────────────────────────────────


def test_ac_s16_agreement_comment_is_dropped():
    assert rule_label("موافقم، هر وقت فرصت داشتید انجامش بدید") == RULE_DROPPED


def test_short_comments_are_dropped():
    assert rule_label("will check") == RULE_DROPPED
    assert rule_label("@sara 👍") == RULE_DROPPED


def test_bare_acknowledgements_are_dropped():
    for text in (
        "ok, thanks a lot!",
        "مرسی، ممنون از پیگیری",
        "انجام شد 👍👍👍👍👍👍👍👍",
        "Done. Thank you!!!",
    ):
        assert rule_label(text) == RULE_DROPPED, text


def test_ack_prefix_does_not_drop_technical_content():
    assert rule_label("ok, I found the cause: reaction_id is null in group payloads") == RULE_KEPT
    assert rule_label("مرسی. مشکل از سرویس fan-out هست که پیام گروهی رو رد میکنه") == RULE_KEPT


def test_mentions_and_markdown_do_not_count_towards_length():
    assert (
        rule_label("@someone_with_a_long_username `x` [ok](https://example.com/very/long)")
        == RULE_DROPPED
    )


# ── talk weights (slice 13, A.6) ─────────────────────────────────────────────


def test_talk_weight_follows_label_and_confidence():
    from app.search.comment_rules import talk_weight

    assert talk_weight(RULE_KEPT) == 1.0
    assert talk_weight(RULE_DROPPED) == 0.0
    assert talk_weight("this_problem", 0.9) == 1.0
    assert talk_weight("other_problem", 0.9) == 0.5
    assert talk_weight("process", 0.9) == 0.0
    assert talk_weight("ack", 0.95) == 0.0
    # Below 0.6 confidence, any Jev label counts as used, fully.
    assert talk_weight("ack", 0.4) == 1.0
    assert talk_weight("other_problem", 0.5) == 1.0


def test_build_documents_reads_jev_labels_with_confidence():
    comments = [
        _comment(1, "The reaction id is null in the group payload, see the logs"),
        _comment(2, "Let's schedule this for the next sprint planning meeting please"),
        _comment(3, "Unsure label but long enough technical text about fan-out"),
    ]
    labels = {1: ("this_problem", 0.9), 2: ("process", 0.9), 3: ("process", 0.3)}
    docs = build_documents(_item(), comments, labels)
    assert [t.timeline_id for t in docs.talk] == [1, 3]
