from infrastructure.ai.spatial_query_parser import (
    has_spatial_relation,
    parse_spatial_relation,
)
from infrastructure.ai.yolo_class_catalog import apply_catalog_fallback
from domain.value_objects.semantic_query import StructuredQuery


def test_parse_spatial_relation_es() -> None:
    parsed = parse_spatial_relation("coches cerca de una rotonda")
    assert parsed is not None
    assert parsed.relation == "near"
    assert "coche" in parsed.target_fragment.lower() or parsed.target_fragment.lower() == "coches"
    assert "rotonda" in parsed.reference_fragment.lower()


def test_parse_spatial_relation_en() -> None:
    parsed = parse_spatial_relation("cars near buildings")
    assert parsed is not None
    assert parsed.target_fragment.lower() == "cars"
    assert parsed.reference_fragment.lower() == "buildings"
    assert parsed.relation == "near"


def test_has_spatial_relation_false_for_simple() -> None:
    assert has_spatial_relation("coches") is False
    assert has_spatial_relation("piscinas azules") is False


def test_apply_catalog_fallback_spatial_target_reference() -> None:
    structured = StructuredQuery(
        intent="unknown",
        detected_language="es",
        object_label=None,
        canonical_label=None,
        clase_yolo_candidates=[],
        attributes=[],
        reasoning="",
    )
    resolved = apply_catalog_fallback(structured, "coches cerca de rotonda")
    assert resolved.intent == "search_spatial"
    assert resolved.relation == "near"
    assert resolved.target_canonical_label == "vehicle"
    assert "car" in resolved.target_clase_yolo
    assert resolved.reference_canonical_label == "roundabout"
    assert resolved.reference_clase_yolo == ["roundabout"]
    # Output classes must be target, never only the reference.
    assert "roundabout" not in resolved.clase_yolo_candidates
    assert "car" in resolved.clase_yolo_candidates


def test_apply_catalog_fallback_does_not_pick_reference_as_class() -> None:
    structured = StructuredQuery(
        intent="search_class",
        detected_language="es",
        object_label="coches",
        canonical_label="vehicle",
        clase_yolo_candidates=["car"],
        attributes=[],
        reasoning="",
    )
    resolved = apply_catalog_fallback(structured, "coches cerca de una rotonda")
    assert resolved.intent == "search_spatial"
    assert resolved.target_canonical_label == "vehicle"
    assert resolved.reference_canonical_label == "roundabout"


def test_apply_catalog_fallback_llm_spatial_promoted() -> None:
    structured = StructuredQuery(
        intent="search_class",
        detected_language="en",
        object_label="cars",
        canonical_label="vehicle",
        clase_yolo_candidates=["car"],
        attributes=[],
        reasoning="",
        target_label="cars",
        target_canonical_label="vehicle",
        reference_label="buildings",
        reference_canonical_label="building",
        relation="near",
    )
    resolved = apply_catalog_fallback(structured, "cars near buildings")
    assert resolved.intent == "search_spatial"
    assert resolved.reference_canonical_label == "building"
