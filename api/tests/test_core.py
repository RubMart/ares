import pytest

from infrastructure.ai.attribute_catalog import (
    build_clip_embedding_text,
    extract_attributes_from_query,
    normalize_attributes,
)
from infrastructure.ai.yolo_class_catalog import (
    apply_catalog_fallback,
    find_catalog_entry,
    resolve_clase_yolo_from_canonical,
    resolve_clase_yolo_from_query,
    YOLO_CLASS_CATALOG,
)
from infrastructure.db.validators import format_pgvector_literal, validate_layer_name
from infrastructure.geo.geojson_serializer import GeoJsonSerializer
from domain.entities.detection import Detection
from domain.value_objects.semantic_query import StructuredQuery


def test_validate_layer_name_ok() -> None:
    assert validate_layer_name("madrid_detections_example") == "madrid_detections_example"


def test_validate_layer_name_invalid() -> None:
    with pytest.raises(ValueError):
        validate_layer_name("bad-name")


def test_format_pgvector_literal() -> None:
    assert format_pgvector_literal([1.0, 2.0]) == "[1.00000000,2.00000000]"


def test_resolve_clase_yolo_from_canonical() -> None:
    classes = resolve_clase_yolo_from_canonical("swimming pool")
    assert "swimming_pool" in classes
    assert "swimming pool" in classes


def test_resolve_clase_yolo_from_canonical_synonym() -> None:
    classes = resolve_clase_yolo_from_canonical("cars")
    assert "car" in classes


def test_resolve_clase_yolo_from_query_plural_es() -> None:
    classes = resolve_clase_yolo_from_query("coches")
    assert "car" in classes


def test_resolve_clase_yolo_from_query_singular_es() -> None:
    classes = resolve_clase_yolo_from_query("coche")
    assert "car" in classes


def test_normalize_attributes_es_to_en() -> None:
    assert normalize_attributes(["rojos", "rojo"]) == ["red"]
    assert normalize_attributes(["azul", "blue"]) == ["blue"]


def test_extract_attributes_from_query() -> None:
    assert extract_attributes_from_query("coches rojos") == ["red"]
    assert extract_attributes_from_query("red cars") == ["red"]


def test_build_clip_embedding_text_with_attributes() -> None:
    structured = StructuredQuery(
        intent="search_class",
        detected_language="es",
        object_label="coches rojos",
        canonical_label="vehicle",
        clase_yolo_candidates=["car"],
        attributes=["red"],
        reasoning="",
    )
    assert build_clip_embedding_text(structured, "coches rojos") == "red vehicle"


def test_build_clip_embedding_text_without_attributes() -> None:
    structured = StructuredQuery(
        intent="search_class",
        detected_language="es",
        object_label="coches",
        canonical_label="vehicle",
        clase_yolo_candidates=["car"],
        attributes=[],
        reasoning="",
    )
    assert build_clip_embedding_text(structured, "coches") == "coches"


def test_apply_catalog_fallback_replaces_llm_synonyms() -> None:
    structured = StructuredQuery(
        intent="search_class",
        detected_language="es",
        object_label="piscinas",
        canonical_label="swimming pool",
        clase_yolo_candidates=["piscina", "piscinas", "alberca", "albercas"],
        attributes=[],
        reasoning="",
    )
    resolved = apply_catalog_fallback(structured, "piscinas")
    assert resolved.clase_yolo_candidates == ["swimming_pool", "swimming pool"]


def test_apply_catalog_fallback_coches_rojos() -> None:
    structured = StructuredQuery(
        intent="search_attribute",
        detected_language="es",
        object_label=None,
        canonical_label=None,
        clase_yolo_candidates=[],
        attributes=[],
        reasoning="",
    )
    resolved = apply_catalog_fallback(structured, "coches rojos")
    assert resolved.intent == "search_class"
    assert "car" in resolved.clase_yolo_candidates
    assert resolved.canonical_label == "vehicle"
    assert resolved.attributes == ["red"]


def test_apply_catalog_fallback_fixes_unknown_intent() -> None:
    structured = StructuredQuery(
        intent="unknown",
        detected_language="es",
        object_label=None,
        canonical_label=None,
        clase_yolo_candidates=[],
        attributes=[],
        reasoning="",
    )
    resolved = apply_catalog_fallback(structured, "coches")
    assert resolved.intent == "search_class"
    assert "car" in resolved.clase_yolo_candidates
    assert resolved.canonical_label == "vehicle"


@pytest.mark.parametrize(
    "query,expected_label",
    [
        ("piscinas", "swimming pool"),
        ("piscinas.", "swimming pool"),
        ("paneles solares", "photovoltaic panel"),
        ("panel solares", "photovoltaic panel"),
        ("placa solar", "photovoltaic panel"),
        ("placas solares", "photovoltaic panel"),
        ("fotovoltaicos", "photovoltaic panel"),
        ("campos deportivos", "sports field"),
        ("buscar piscinas", "swimming pool"),
        ("piscinas azules", "swimming pool"),
        ("edificios", "building"),
        ("peatones", "pedestrian"),
        ("rotondas", "roundabout"),
        ("autobuses", "vehicle"),
        ("albercas", "swimming pool"),
    ],
)
def test_find_catalog_entry_plural_and_phrase_forms(query: str, expected_label: str) -> None:
    entry = find_catalog_entry(query)
    assert entry is not None
    assert entry.canonical_label == expected_label


@pytest.mark.parametrize(
    "query",
    [
        "piscinas",
        "paneles solares",
        "placas solares",
        "edificios",
        "peatones",
        "coches",
        "piscinas.",
        "panel solares",
    ],
)
def test_apply_catalog_fallback_plural_queries(query: str) -> None:
    structured = StructuredQuery(
        intent="unknown",
        detected_language="es",
        object_label=None,
        canonical_label=None,
        clase_yolo_candidates=[],
        attributes=[],
        reasoning="",
    )
    resolved = apply_catalog_fallback(structured, query)
    assert resolved.intent == "search_class"
    assert resolved.clase_yolo_candidates


def test_catalog_has_bilingual_entries() -> None:
    assert len(YOLO_CLASS_CATALOG) >= 7
    pool_entry = next(
        entry for entry in YOLO_CLASS_CATALOG if entry.canonical_label == "swimming pool"
    )
    assert pool_entry.synonyms_es
    assert pool_entry.synonyms_en


def test_geojson_serializer() -> None:
    detection = Detection(
        id=1,
        layer="madrid_detections_example",
        tile_id="16/32101/24711",
        clase_yolo="swimming_pool",
        modelo_deteccion="swimming-pool-detector",
        confianza=0.5,
        similarity=0.9,
        geom_geojson={"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]},
    )
    structured = StructuredQuery(
        intent="search_class",
        detected_language="es",
        object_label="piscina",
        canonical_label="swimming pool",
        clase_yolo_candidates=["swimming_pool", "swimming pool"],
        attributes=[],
        reasoning="test",
    )
    payload = GeoJsonSerializer.to_feature_collection(
        detections=[detection],
        query="piscinas",
        structured_query=structured,
        layers_searched=["madrid_detections_example"],
    )
    assert payload["type"] == "FeatureCollection"
    assert len(payload["features"]) == 1
    assert payload["metadata"]["detected_language"] == "es"
