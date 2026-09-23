"""Support report composition (slice 05, FR-10, BR-34) — pure, no I/O.

``compose_report`` validates a submission against a template snapshot and
renders the markdown that becomes the item's description. The description is
the record: field values are never stored as columns, so a later template
edit can't rewrite an existing report (BR-35).

Output::

    **Report template:** Online class problem

    - **Class time:** 2026-09-21 18:00
    - **Class name:** IELTS B2 — Evening

    ---

    <free description, verbatim>

Empty optional fields are omitted; the rule and free description are omitted
when the description is empty. User-entered text is escaped so a value can't
break out of its list item (``lib/markdown.js`` honours backslash escapes).
"""

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlparse

from app.db.models.support_template import FieldType

#: Characters the frontend markdown parser treats as syntax inside a line.
_MD_SPECIAL = re.compile(r"([\\`*_\[\]()~@<>#|!])")


@dataclass(frozen=True)
class FieldSpec:
    id: int
    label: str
    field_type: str
    is_required: bool = False
    #: Single select only: ``[{"value": ..., "label": ...}]``.
    options: tuple[dict, ...] = ()


@dataclass(frozen=True)
class TemplateSpec:
    id: int
    name: str
    fields: tuple[FieldSpec, ...] = field(default_factory=tuple)


@dataclass
class Composition:
    markdown: str
    #: ``{field_id: message}``; empty when the submission is valid.
    errors: dict[str, str]
    #: Normalized values keyed by field id — the forensic copy for the ``filed`` event.
    values: dict[str, Any]


def escape_md(text: str) -> str:
    """Backslash-escape inline markdown syntax in user-entered text."""
    return _MD_SPECIAL.sub(r"\\\1", text)


def _is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


def _clean(field: FieldSpec, raw: Any) -> tuple[Any, str, str | None]:
    """Validate one non-blank value. Returns ``(normalized, rendered, error)``."""
    ft = field.field_type

    if ft in (FieldType.short_text.value, FieldType.long_text.value):
        if not isinstance(raw, str):
            return None, "", "Enter text."
        text = raw.strip()
        if ft == FieldType.short_text.value:
            text = " ".join(text.split())  # one line
            if len(text) > 500:
                return None, "", "Keep this under 500 characters."
            return text, escape_md(text), None
        return text, text, None  # long text is rendered line by line by the caller

    if ft == FieldType.number.value:
        if isinstance(raw, bool):
            return None, "", "Enter a number."
        try:
            num = Decimal(str(raw).strip())
        except InvalidOperation:
            return None, "", "Enter a number."
        if not num.is_finite():
            return None, "", "Enter a number."
        normalized = int(num) if num == num.to_integral_value() else float(num)
        return normalized, str(normalized), None

    if ft == FieldType.date.value:
        try:
            d = date.fromisoformat(str(raw).strip())
        except ValueError:
            return None, "", "Enter a date as YYYY-MM-DD."
        return d.isoformat(), d.isoformat(), None

    if ft == FieldType.datetime.value:
        try:
            dt = datetime.fromisoformat(str(raw).strip())
        except ValueError:
            return None, "", "Enter a date and time."
        dt = dt.replace(second=0, microsecond=0)
        return dt.isoformat(), dt.strftime("%Y-%m-%d %H:%M"), None

    if ft == FieldType.single_select.value:
        for opt in field.options:
            if str(opt.get("value")) == str(raw):
                return opt.get("value"), escape_md(str(opt.get("label", opt.get("value")))), None
        return None, "", "Pick one of the listed options."

    if ft == FieldType.url.value:
        text = str(raw).strip()
        parsed = urlparse(text)
        if parsed.scheme not in ("http", "https") or not parsed.netloc or " " in text:
            return None, "", "Enter a full link starting with http:// or https://."
        return text, escape_md(text), None

    return None, "", "Unsupported field type."


def compose_report(
    template: TemplateSpec, values: dict[Any, Any], free_text: str | None,
) -> Composition:
    """Validate ``values`` (keyed by field id) and render the report markdown."""
    by_id = {str(k): v for k, v in (values or {}).items()}
    errors: dict[str, str] = {}
    normalized: dict[str, Any] = {}
    lines: list[str] = []

    for f in template.fields:
        key = str(f.id)
        raw = by_id.get(key)
        if _is_blank(raw):
            if f.is_required:
                errors[key] = "This field is required."
            continue
        value, rendered, error = _clean(f, raw)
        if error:
            errors[key] = error
            continue
        normalized[key] = value
        label = escape_md(f.label)
        if f.field_type == FieldType.long_text.value:
            body = [escape_md(line) for line in rendered.splitlines() if line.strip()]
            lines.append(f"- **{label}:**")
            lines.extend(f"> {line}" for line in body)
        else:
            lines.append(f"- **{label}:** {rendered}")

    if errors:
        return Composition(markdown="", errors=errors, values={})

    parts = [f"**Report template:** {escape_md(template.name)}"]
    if lines:
        parts.append("\n".join(lines))
    description = (free_text or "").strip()
    if description:
        parts.append("---")
        parts.append(description)
    return Composition(markdown="\n\n".join(parts), errors={}, values=normalized)
