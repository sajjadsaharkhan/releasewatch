"""Search request schemas (slice 14: similar-item suggestions, A.9)."""

from typing import Any, Literal

from pydantic import BaseModel, Field


class SimilarItemsRequest(BaseModel):
    """Payload for POST /search/similar (FR-S08–S10).

    ``context`` picks the consumer's candidate rule: ``support`` sees only open
    support reports of the project (BR-S07); ``tech`` sees every non-cancelled
    item of the project (BR-S08). ``template_id`` + ``values`` compose the
    support draft's template block the way ``compose_report`` (05) will when
    the report is submitted.
    """

    context: Literal["support", "tech"]
    project_id: int
    title: str = Field(min_length=1, max_length=500)
    description: str | None = None
    template_id: int | None = None
    values: dict[str, Any] = Field(default_factory=dict)
