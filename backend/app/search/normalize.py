"""Search text normalization (slice 12, engine PRD Appendix A.2).

Pure functions, applied identically to indexed text and to queries:

- ``normalize`` — what the embedding model sees: NFC, Arabic → Persian
  letters, Persian/Arabic digits → ASCII, no diacritics, tatweel, ZWJ or
  direction marks, one ZWNJ at most (none beside a space), trimmed whitespace.
- ``fold`` — what the trigram keyword index sees: ``normalize`` plus no ZWNJ,
  alef variants → ``ا``, lowercase. ``ثبت‌نام`` and ``ثبتنام`` fold the same.
- ``strip_markdown`` — descriptions and comments lose links (kept as their
  text), code blocks, inline code, and ``@mentions`` before either of the above.

The PoC's Persian↔English bridge is deliberately absent: bge-m3 gains nothing
from it (A.2).
"""

import re
import unicodedata

ZWNJ = "\u200c"

_LETTERS = str.maketrans(
    {
        "ي": "ی",
        "ى": "ی",
        "ك": "ک",
        "ة": "ه",
        # Persian and Arabic-Indic digits.
        **{chr(0x06F0 + i): str(i) for i in range(10)},
        **{chr(0x0660 + i): str(i) for i in range(10)},
    }
)

#: Harakat, superscript alef, tatweel, ZWJ, BOM, and bidi controls.
_DROP = re.compile(
    "[\u064b-\u065f\u0670\u0640\u200d\ufeff\u200e\u200f\u202a-\u202e\u2066-\u2069]"
)
_ZWNJ_RUN = re.compile(f"{ZWNJ}+")
_ZWNJ_BY_SPACE = re.compile(rf"\s*{ZWNJ}\s+|\s+{ZWNJ}\s*")
_SPACES = re.compile(r"\s+")

_FOLD = str.maketrans({"آ": "ا", "أ": "ا", "إ": "ا", "ٱ": "ا", "ؤ": "و", ZWNJ: None})


def normalize(text: str | None) -> str:
    if not text:
        return ""
    t = unicodedata.normalize("NFC", text).translate(_LETTERS)
    t = _DROP.sub("", t)
    t = _ZWNJ_RUN.sub(ZWNJ, t)
    t = _ZWNJ_BY_SPACE.sub(" ", t)
    t = t.strip(f" \t\r\n{ZWNJ}")
    return _SPACES.sub(" ", t)


def fold(text: str | None) -> str:
    return normalize(text).translate(_FOLD).lower()


_FENCED = re.compile(r"```.*?(```|$)", re.S)
_IMAGE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")
_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_INLINE_CODE = re.compile(r"`[^`\n]*`")
_MENTION = re.compile(r"(?<![\w@])@[\w.\-]+")
_EMPHASIS = re.compile(r"(\*\*|__|~~|(?<!\w)[*_](?=\S)|(?<=\S)[*_](?!\w))")
_LINE_MARKERS = re.compile(r"^\s{0,3}(#{1,6}\s+|>\s?|[-*+]\s+|\d+[.)]\s+)", re.M)
_HR = re.compile(r"^\s*(-{3,}|\*{3,}|_{3,})\s*$", re.M)


def strip_markdown(text: str | None, *, keep_inline_code: bool = False) -> str:
    """Markdown → plain text. ``keep_inline_code`` keeps what is inside single
    backticks (the keyword text wants ``/api/v1/...`` and error codes)."""
    if not text:
        return ""
    t = _FENCED.sub(" ", text)
    t = _IMAGE.sub(r"\1", t)
    t = _LINK.sub(r"\1", t)
    t = _INLINE_CODE.sub((lambda m: f" {m.group(0)[1:-1]} ") if keep_inline_code else " ", t)
    t = _MENTION.sub(" ", t)
    t = _HR.sub(" ", t)
    t = _LINE_MARKERS.sub("", t)
    t = _EMPHASIS.sub("", t)
    return _SPACES.sub(" ", t).strip()
