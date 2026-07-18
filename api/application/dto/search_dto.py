from dataclasses import dataclass

from domain.value_objects.search_filters import SearchFilters
from domain.value_objects.semantic_query import StructuredQuery


@dataclass(frozen=True)
class SearchRequestDTO:
    query: str
    filters: SearchFilters


@dataclass(frozen=True)
class SearchResponseDTO:
    feature_collection: dict
    structured_query: StructuredQuery
