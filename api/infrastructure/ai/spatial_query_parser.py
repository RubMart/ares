from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from domain.value_objects.semantic_query import StructuredQuery


SPATIAL_RELATION_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            r"^(?P<target>.+?)\s+(?:cerca\s+de|junto\s+a|alrededor\s+de)\s+(?P<reference>.+)$",
            re.IGNORECASE,
        ),
        "near",
    ),
    (
        re.compile(
            r"^(?P<target>.+?)\s+(?:near|next\s+to|close\s+to|around)\s+(?P<reference>.+)$",
            re.IGNORECASE,
        ),
        "near",
    ),
]

ARTICLE_PREFIX = re.compile(
    r"^(?:una?|unos|unas|the|a|an|la|las|el|los|del?)\s+",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SpatialParseResult:
    target_fragment: str
    reference_fragment: str
    relation: str


def _normalize_fragment(text: str) -> str:
    cleaned = ARTICLE_PREFIX.sub("", text.strip())
    cleaned = re.sub(r"[^\w\s]", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def parse_spatial_relation(query: str) -> SpatialParseResult | None:
    normalized = unicodedata.normalize("NFKC", query.strip())
    if not normalized:
        return None

    for pattern, relation in SPATIAL_RELATION_PATTERNS:
        match = pattern.match(normalized)
        if not match:
            continue
        target = _normalize_fragment(match.group("target"))
        reference = _normalize_fragment(match.group("reference"))
        if target and reference:
            return SpatialParseResult(
                target_fragment=target,
                reference_fragment=reference,
                relation=relation,
            )
    return None


def has_spatial_relation(query: str) -> bool:
    return parse_spatial_relation(query) is not None


def merge_spatial_parse_into_structured(
    structured: StructuredQuery,
    parsed: SpatialParseResult,
) -> StructuredQuery:
    updates: dict[str, object] = {
        "intent": "search_spatial",
        "relation": parsed.relation,  # type: ignore[dict-item]
        "target_label": structured.target_label or parsed.target_fragment,
        "reference_label": structured.reference_label or parsed.reference_fragment,
        "object_label": structured.object_label or parsed.target_fragment,
    }
    return structured.model_copy(update=updates)
