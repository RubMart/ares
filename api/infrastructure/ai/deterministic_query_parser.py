from __future__ import annotations

from typing import Literal

from domain.value_objects.semantic_query import StructuredQuery
from infrastructure.ai.attribute_catalog import (
    COLOR_SYNONYMS,
    extract_attributes_from_query,
)
from infrastructure.ai.spatial_query_parser import parse_spatial_relation
from infrastructure.ai.yolo_class_catalog import (
    YOLO_CLASS_CATALOG,
    YoloClassEntry,
    _normalize_text,
    find_catalog_entry_exact,
)

_REASONING = "deterministic catalog parse"

_ES_COLOR_TOKENS = {
    key
    for key, value in COLOR_SYNONYMS.items()
    if key
    not in {
        "red",
        "blue",
        "green",
        "black",
        "white",
        "yellow",
        "gray",
        "grey",
        "orange",
    }
}
_EN_COLOR_TOKENS = {
    "red",
    "blue",
    "green",
    "black",
    "white",
    "yellow",
    "gray",
    "grey",
    "orange",
}


def _detect_language(query: str) -> Literal["es", "en", "unknown"]:
    tokens = set(_normalize_text(query).split())
    if not tokens:
        return "unknown"

    es_terms: set[str] = set(_ES_COLOR_TOKENS)
    en_terms: set[str] = set(_EN_COLOR_TOKENS)
    for entry in YOLO_CLASS_CATALOG:
        for synonym in entry.synonyms_es:
            es_terms.add(_normalize_text(synonym))
        for synonym in entry.synonyms_en:
            en_terms.add(_normalize_text(synonym))

    es_hits = sum(1 for token in tokens if token in es_terms)
    en_hits = sum(1 for token in tokens if token in en_terms)
    if es_hits > en_hits:
        return "es"
    if en_hits > es_hits:
        return "en"
    return "unknown"


def _build_class_structured(
    *,
    query: str,
    entry: YoloClassEntry,
    label: str,
) -> StructuredQuery:
    attributes = extract_attributes_from_query(query)
    classes = list(entry.clase_yolo)
    return StructuredQuery(
        intent="search_class",
        detected_language=_detect_language(query),
        object_label=label,
        canonical_label=entry.canonical_label,
        clase_yolo_candidates=classes,
        attributes=attributes,
        reasoning=_REASONING,
        target_label=label,
        target_canonical_label=entry.canonical_label,
        target_clase_yolo=classes,
    )


def _build_spatial_structured(
    *,
    query: str,
    target_label: str,
    reference_label: str,
    target_entry: YoloClassEntry,
    reference_entry: YoloClassEntry,
    relation: str,
) -> StructuredQuery:
    attributes = extract_attributes_from_query(target_label)
    target_classes = list(target_entry.clase_yolo)
    return StructuredQuery(
        intent="search_spatial",
        detected_language=_detect_language(query),
        object_label=target_label,
        canonical_label=target_entry.canonical_label,
        clase_yolo_candidates=target_classes,
        attributes=attributes,
        reasoning=_REASONING,
        relation=relation,  # type: ignore[arg-type]
        target_label=target_label,
        target_canonical_label=target_entry.canonical_label,
        target_clase_yolo=target_classes,
        reference_label=reference_label,
        reference_canonical_label=reference_entry.canonical_label,
        reference_clase_yolo=list(reference_entry.clase_yolo),
    )


def try_deterministic_parse(query: str) -> StructuredQuery | None:
    """Return StructuredQuery when the NL query is unambiguous; else None (use LLM)."""
    cleaned_query = query.strip()
    if not cleaned_query:
        return None

    parsed = parse_spatial_relation(cleaned_query)
    if parsed is not None:
        target_entry = find_catalog_entry_exact(parsed.target_fragment)
        reference_entry = find_catalog_entry_exact(parsed.reference_fragment)
        if target_entry is None or reference_entry is None:
            return None
        return _build_spatial_structured(
            query=cleaned_query,
            target_label=parsed.target_fragment,
            reference_label=parsed.reference_fragment,
            target_entry=target_entry,
            reference_entry=reference_entry,
            relation=parsed.relation,
        )

    entry = find_catalog_entry_exact(cleaned_query)
    if entry is None:
        return None

    return _build_class_structured(
        query=cleaned_query,
        entry=entry,
        label=cleaned_query,
    )
