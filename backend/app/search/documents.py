"""What gets indexed for one item (slice 12, engine PRD Appendix A.3).

``build_documents`` is pure: it takes the item, its comments, and their
labels and returns the texts to embed and the keyword text. It decides what
is searchable; ``app/tasks/search_index.py`` only stores the result.

- ``title`` — the normalized title.
- ``body_chunks`` — title + description + reproduction steps, normalized, no
  field labels. Chunked past ~500 tokens. The only input for same-problem
  candidates later (principle S4), so comments never reach it.
- ``talk`` — one entry per comment whose label says it is used for search.
- ``keyword_text`` — title + description + cURL URL paths + item labels,
  folded, for the trigram channel. Host, headers, query string and body of the
  cURL are dropped, so no secret reaches the index.

Token counts are approximated as 1 token ≈ 4 characters for both Persian and
English, which keeps chunks inside bge-m3's window without calling its tokenizer.
"""

import hashlib
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

from app.search.comment_rules import talk_weight
from app.search.normalize import fold, normalize, strip_markdown

CHARS_PER_TOKEN = 4
#: A body longer than this is chunked (~500 tokens).
CHUNK_THRESHOLD_CHARS = 500 * CHARS_PER_TOKEN
#: Chunk size and overlap (~400 tokens, ~50 tokens).
CHUNK_CHARS = 400 * CHARS_PER_TOKEN
OVERLAP_CHARS = 50 * CHARS_PER_TOKEN


@dataclass(frozen=True)
class TalkDoc:
    timeline_id: int
    text: str
    is_internal: bool


@dataclass(frozen=True)
class Documents:
    title: str
    body_chunks: list[str]
    talk: list[TalkDoc] = field(default_factory=list)
    keyword_text: str = ""


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:32]


_URL = re.compile(r"""https?://[^\s'"\\]+""")


def curl_paths(curl_command: str | None) -> list[str]:
    """URL paths in a cURL command, in order, without host or query string."""
    if not curl_command:
        return []
    paths: list[str] = []
    for url in _URL.findall(curl_command):
        path = urlsplit(url).path
        if path and path != "/" and path not in paths:
            paths.append(path)
    return paths


def _steps_text(steps: Any) -> list[str]:
    parts: list[str] = []
    for step in steps or []:
        if not isinstance(step, Mapping):
            continue
        for key in ("description", "expected_result", "actual_result"):
            value = normalize(strip_markdown(step.get(key)))
            if value:
                parts.append(value)
    return parts


def chunk(text: str) -> list[str]:
    """Split ``text`` into overlapping chunks at word boundaries."""
    if len(text) <= CHUNK_THRESHOLD_CHARS:
        return [text] if text else []
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + CHUNK_CHARS, len(text))
        if end < len(text):
            cut = text.rfind(" ", start + CHUNK_CHARS // 2, end + 1)
            end = cut if cut > start else end
        chunks.append(text[start:end].strip())
        if end >= len(text):
            break
        nxt = end - OVERLAP_CHARS
        space = text.find(" ", nxt)
        start = space + 1 if 0 <= space < end else nxt
    return [c for c in chunks if c]


def body_text(item: Any) -> str:
    """The body rule as one string: title + description + reproduction steps,
    normalized (principle S4 — comments are never part of it). This is the
    draft text of an unwritten report for ``same_problem_candidates`` (14) and
    the chunk input of ``build_documents``."""
    title = normalize(item.title)
    description = normalize(strip_markdown(item.description))
    return " ".join(p for p in (title, description, *_steps_text(item.reproduction_steps)) if p)


def build_documents(
    item: Any,
    comments: Iterable[Any],
    labels: Mapping[int, str | tuple[str, float | None]],
) -> Documents:
    """``item`` needs ``title``, ``description``, ``reproduction_steps``,
    ``curl_command`` and ``labels``; each comment ``id``, ``body`` and
    ``is_internal``; ``labels`` maps a comment id to its comment label, or to
    ``(label, confidence)`` for a Jev label."""
    title = normalize(item.title)
    body = body_text(item)

    talk = []
    for c in comments:
        label = labels.get(c.id)
        label, confidence = label if isinstance(label, tuple) else (label, None)
        if talk_weight(label, confidence) <= 0:
            continue
        text = normalize(strip_markdown(c.body))
        if text:
            talk.append(TalkDoc(timeline_id=c.id, text=text, is_internal=bool(c.is_internal)))

    keyword_parts = [
        item.title,
        strip_markdown(item.description, keep_inline_code=True),
        *curl_paths(item.curl_command),
        *(item.labels or []),
    ]
    keyword_text = fold(" ".join(p for p in keyword_parts if p))

    return Documents(title=title, body_chunks=chunk(body), talk=talk, keyword_text=keyword_text)
