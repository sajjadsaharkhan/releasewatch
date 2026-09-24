"""DomainError — the one shape every domain-rule 409 takes.

See docs/phase-2/00-README.md → Errors: a domain rule violation returns 409
with ``{detail, code, allowed}``. Raised by Workflow-backed transitions today
(``app/workflow.py``, ``IssueService.transition``); Policy (slice 04) reuses
it for the same reason.
"""

from fastapi import Request
from fastapi.responses import JSONResponse


class DomainError(Exception):
    """A domain rule refused an action. Carries the fields the API contract requires."""

    def __init__(
        self,
        status_code: int,
        detail: str,
        code: str,
        allowed: list[str] | None = None,
        errors: dict[str, str] | None = None,
        extra: dict | None = None,
    ) -> None:
        self.status_code = status_code
        self.detail = detail
        self.code = code
        self.allowed = allowed
        #: Per-field messages, e.g. ``{field_id: "This field is required."}`` (slice 05).
        self.errors = errors
        #: Rule-specific fields merged into the body, e.g. ``suggested_id`` (slice 06).
        self.extra = extra
        super().__init__(detail)


async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    body: dict = {"detail": exc.detail, "code": exc.code}
    if exc.allowed is not None:
        body["allowed"] = exc.allowed
    if exc.errors is not None:
        body["errors"] = exc.errors
    if exc.extra:
        body.update(exc.extra)
    return JSONResponse(status_code=exc.status_code, content=body)
