from typing import Literal

from pydantic import BaseModel, Field


class StructuredQuery(BaseModel):
    intent: Literal["search_class", "search_attribute", "unknown"]
    detected_language: Literal["es", "en", "unknown"]
    object_label: str | None = None
    canonical_label: str | None = None
    clase_yolo_candidates: list[str] = Field(default_factory=list)
    attributes: list[str] = Field(default_factory=list)
    reasoning: str = ""
