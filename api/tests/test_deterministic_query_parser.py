from infrastructure.ai.deterministic_query_parser import try_deterministic_parse
from infrastructure.ai.yolo_class_catalog import find_catalog_entry_exact


def test_find_catalog_entry_exact_hit_piscinas() -> None:
    entry = find_catalog_entry_exact("piscinas")
    assert entry is not None
    assert entry.canonical_label == "swimming pool"


def test_find_catalog_entry_exact_miss_ambiguous() -> None:
    assert find_catalog_entry_exact("vehículos aparcados") is None


def test_find_catalog_entry_exact_strips_color() -> None:
    entry = find_catalog_entry_exact("coches rojos")
    assert entry is not None
    assert entry.canonical_label == "vehicle"


def test_try_deterministic_parse_class() -> None:
    structured = try_deterministic_parse("piscinas")
    assert structured is not None
    assert structured.intent == "search_class"
    assert structured.target_canonical_label == "swimming pool"
    assert structured.reasoning == "deterministic catalog parse"


def test_try_deterministic_parse_class_with_color() -> None:
    structured = try_deterministic_parse("coches rojos")
    assert structured is not None
    assert structured.intent == "search_class"
    assert structured.target_canonical_label == "vehicle"
    assert structured.attributes == ["red"]
    assert structured.detected_language == "es"


def test_try_deterministic_parse_spatial() -> None:
    structured = try_deterministic_parse("coches cerca de rotonda")
    assert structured is not None
    assert structured.intent == "search_spatial"
    assert structured.relation == "near"
    assert structured.target_canonical_label == "vehicle"
    assert structured.reference_canonical_label == "roundabout"
    assert "roundabout" not in structured.clase_yolo_candidates


def test_try_deterministic_parse_personas_cerca_de_piscina() -> None:
    structured = try_deterministic_parse("personas cerca de una piscina")
    assert structured is not None
    assert structured.intent == "search_spatial"
    assert structured.relation == "near"
    assert structured.target_canonical_label == "pedestrian"
    assert structured.reference_canonical_label == "swimming pool"
    assert "pedestrian" in structured.clase_yolo_candidates


def test_try_deterministic_parse_spatial_incomplete() -> None:
    assert try_deterministic_parse("coches cerca de algo") is None


def test_try_deterministic_parse_garbage() -> None:
    assert try_deterministic_parse("quiero ver cosas raras") is None


def test_try_deterministic_parse_color_only() -> None:
    assert try_deterministic_parse("rojos") is None
