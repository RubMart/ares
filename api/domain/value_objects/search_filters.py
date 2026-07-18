from dataclasses import dataclass


@dataclass(frozen=True)
class SearchFilters:
    top_k: int
    per_layer_limit: int
    min_confidence: float
