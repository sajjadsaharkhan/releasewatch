"""The comment rule — which comments reach the search index while Jev is off
(slice 12, engine PRD FR-S16, Appendix A.6).

``rule_label(text)`` strips mentions and markdown, removes every
acknowledgement and courtesy phrase below, and keeps the comment only if at
least ``MIN_CHARS`` letters or digits are left. So ``موافقم، هر وقت فرصت داشتید
انجامش بدید`` is dropped (nothing but agreement and a scheduling nicety), while
``ok, I found the cause: …`` is kept (the rest is technical content).
"""

import re

from app.search.normalize import fold, strip_markdown

RULE_KEPT = "rule_kept"
RULE_DROPPED = "rule_dropped"

#: Labels whose comments are used for search (A.6). Slice 13 adds Jev's
#: ``this_problem`` and ``other_problem``.
USED_LABELS = frozenset({RULE_KEPT})

#: Fewer letters/digits than this, after removing the phrases below, is dropped.
MIN_CHARS = 20

#: Agreement, thanks, acknowledgement, status pings and scheduling niceties —
#: compared folded (no ZWNJ, lowercase), as whole words.
ACK_PHRASES = (
    # Persian
    "موافقم",
    "موافق هستم",
    "اوکی",
    "اوکیه",
    "باشه",
    "حتما",
    "چشم",
    "مرسی",
    "ممنون",
    "ممنونم",
    "سپاس",
    "سپاسگزارم",
    "تشکر",
    "خیلی ممنون",
    "دمت گرم",
    "عالیه",
    "عالی",
    "انجام شد",
    "انجام میشه",
    "انجام میدم",
    "بررسی میکنم",
    "بررسی میشه",
    "پیگیری میکنم",
    "ممنون از پیگیری",
    "مرسی از پیگیری",
    "هر وقت فرصت داشتید",
    "هر وقت فرصت کردید",
    "انجامش بدید",
    "انجامش بدین",
    "انجامش بده",
    "اوکی هست",
    "مشکلی نیست",
    "درسته",
    "بله",
    "نه",
    "سلام",
    "وقت بخیر",
    "خسته نباشید",
    # English
    "ok",
    "okay",
    "k",
    "sure",
    "agreed",
    "agree",
    "i agree",
    "sounds good",
    "lgtm",
    "thanks",
    "thank you",
    "thanks a lot",
    "thx",
    "ty",
    "great",
    "nice",
    "cool",
    "done",
    "will do",
    "will check",
    "on it",
    "noted",
    "got it",
    "yes",
    "no",
    "do it when you have time",
    "when you have time",
    "please",
    "hi",
    "hello",
    "+1",
)

_PHRASES = sorted({fold(p) for p in ACK_PHRASES}, key=len, reverse=True)
_PHRASE_RE = re.compile(r"(?<![\w])(" + "|".join(re.escape(p) for p in _PHRASES) + r")(?![\w])")


def meaningful_chars(text: str) -> int:
    return sum(1 for ch in text if ch.isalnum())


def rule_label(text: str | None) -> str:
    plain = fold(strip_markdown(text))
    if meaningful_chars(plain) < MIN_CHARS:
        return RULE_DROPPED
    rest = _PHRASE_RE.sub(" ", plain)
    return RULE_KEPT if meaningful_chars(rest) >= MIN_CHARS else RULE_DROPPED
