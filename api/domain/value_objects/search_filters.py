from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class SearchFilters:
    top_k: int
    per_layer_limit: int
    min_confidence: float
    spatial_distance_m: float | None = None
    spatial_relation: Literal["near"] | None = None
    target: str | None = None
    reference: str | None = None
