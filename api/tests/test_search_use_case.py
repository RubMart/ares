import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from application.dto.search_dto import SearchRequestDTO
from application.use_cases.search_detections import (
    SearchDetectionsUseCase,
    SearchValidationError,
)
from domain.entities.detection import Detection
from domain.value_objects.search_filters import SearchFilters
from domain.value_objects.semantic_query import StructuredQuery


def _build_use_case(
    *,
    structured: StructuredQuery,
    detection_repository: MagicMock | None = None,
) -> tuple[SearchDetectionsUseCase, MagicMock, MagicMock]:
    query_analyzer = MagicMock()
    query_analyzer.analyze = AsyncMock(return_value=structured)

    text_embedder = MagicMock()
    text_embedder.embed_text.return_value = [0.1, 0.2]

    catalog_repository = MagicMock()
    catalog_layer = MagicMock()
    catalog_layer.nombre_capa = "madrid_detections_example"
    catalog_repository.list_layers = AsyncMock(return_value=[catalog_layer])

    if detection_repository is None:
        detection_repository = MagicMock()
        detection_repository.search_hybrid = AsyncMock(return_value=[])
        detection_repository.search_spatial_near = AsyncMock(return_value=[])

    use_case = SearchDetectionsUseCase(
        query_analyzer=query_analyzer,
        text_embedder=text_embedder,
        catalog_repository=catalog_repository,
        detection_repository=detection_repository,
    )
    return use_case, text_embedder, detection_repository


def test_search_uses_attribute_enriched_embedding_text() -> None:
    structured = StructuredQuery(
        intent="search_class",
        detected_language="es",
        object_label="coches rojos",
        canonical_label="vehicle",
        clase_yolo_candidates=["car", "small vehicle"],
        attributes=["red"],
        reasoning="",
        target_canonical_label="vehicle",
        target_clase_yolo=["car", "small vehicle"],
    )
    use_case, text_embedder, detection_repository = _build_use_case(structured=structured)

    asyncio.run(
        use_case.execute(
            SearchRequestDTO(
                query="coches rojos",
                filters=SearchFilters(top_k=10, per_layer_limit=100, min_confidence=0.25),
            )
        )
    )

    text_embedder.embed_text.assert_called_once_with("red vehicle")
    detection_repository.search_hybrid.assert_awaited_once()
    detection_repository.search_spatial_near.assert_not_awaited()


def test_search_spatial_calls_spatial_near() -> None:
    structured = StructuredQuery(
        intent="search_spatial",
        detected_language="es",
        object_label="coches",
        canonical_label="vehicle",
        clase_yolo_candidates=["car"],
        attributes=[],
        reasoning="",
        relation="near",
        target_label="coches",
        target_canonical_label="vehicle",
        target_clase_yolo=["car", "small vehicle"],
        reference_label="rotonda",
        reference_canonical_label="roundabout",
        reference_clase_yolo=["roundabout"],
    )
    use_case, text_embedder, detection_repository = _build_use_case(structured=structured)

    asyncio.run(
        use_case.execute(
            SearchRequestDTO(
                query="coches cerca de rotonda",
                filters=SearchFilters(top_k=10, per_layer_limit=100, min_confidence=0.0),
            )
        )
    )

    text_embedder.embed_text.assert_called_once_with("vehicle")
    detection_repository.search_spatial_near.assert_awaited_once()
    detection_repository.search_hybrid.assert_not_awaited()
    call_kwargs = detection_repository.search_spatial_near.await_args.kwargs
    assert call_kwargs["target_clase_yolo_list"] == ["car", "small vehicle"]
    assert call_kwargs["reference_clase_yolo_list"] == ["roundabout"]
    assert call_kwargs["distance_m"] == 50.0


def test_search_spatial_override_target_reference() -> None:
    # LLM wrongly classified as roundabout-only; overrides fix it.
    structured = StructuredQuery(
        intent="search_class",
        detected_language="es",
        object_label="rotonda",
        canonical_label="roundabout",
        clase_yolo_candidates=["roundabout"],
        attributes=[],
        reasoning="",
    )
    use_case, _, detection_repository = _build_use_case(structured=structured)

    asyncio.run(
        use_case.execute(
            SearchRequestDTO(
                query="coches cerca de rotonda",
                filters=SearchFilters(
                    top_k=10,
                    per_layer_limit=100,
                    min_confidence=0.0,
                    target="vehicle",
                    reference="roundabout",
                    spatial_relation="near",
                    spatial_distance_m=30,
                ),
            )
        )
    )

    detection_repository.search_spatial_near.assert_awaited_once()
    call_kwargs = detection_repository.search_spatial_near.await_args.kwargs
    assert "car" in call_kwargs["target_clase_yolo_list"]
    assert call_kwargs["reference_clase_yolo_list"] == ["roundabout"]
    assert call_kwargs["distance_m"] == 30


def test_search_spatial_missing_reference_raises() -> None:
    structured = StructuredQuery(
        intent="search_spatial",
        detected_language="es",
        object_label="coches",
        canonical_label="vehicle",
        clase_yolo_candidates=["car"],
        attributes=[],
        reasoning="",
        relation="near",
        target_canonical_label="vehicle",
        target_clase_yolo=["car"],
        reference_clase_yolo=[],
    )
    use_case, _, _ = _build_use_case(structured=structured)

    with pytest.raises(SearchValidationError, match="referencia espacial"):
        asyncio.run(
            use_case.execute(
                SearchRequestDTO(
                    query="coches cerca de algo",
                    filters=SearchFilters(top_k=10, per_layer_limit=100, min_confidence=0.0),
                )
            )
        )


def test_search_inside_relation_not_supported() -> None:
    structured = StructuredQuery(
        intent="search_spatial",
        detected_language="es",
        object_label="coches",
        canonical_label="vehicle",
        clase_yolo_candidates=["car"],
        attributes=[],
        reasoning="",
        relation="inside",
        target_clase_yolo=["car"],
        reference_clase_yolo=["roundabout"],
    )
    use_case, _, _ = _build_use_case(structured=structured)

    with pytest.raises(SearchValidationError, match="inside"):
        asyncio.run(
            use_case.execute(
                SearchRequestDTO(
                    query="coches dentro de rotonda",
                    filters=SearchFilters(top_k=10, per_layer_limit=100, min_confidence=0.0),
                )
            )
        )


def test_search_spatial_embeds_target_not_full_phrase() -> None:
    structured = StructuredQuery(
        intent="search_spatial",
        detected_language="es",
        object_label="coches",
        canonical_label="vehicle",
        clase_yolo_candidates=["car"],
        attributes=[],
        reasoning="",
        relation="near",
        target_canonical_label="vehicle",
        target_clase_yolo=["car"],
        reference_canonical_label="roundabout",
        reference_clase_yolo=["roundabout"],
    )
    detection = Detection(
        id=1,
        layer="madrid_detections_example",
        tile_id="16/1/1",
        clase_yolo="car",
        modelo_deteccion="yolo",
        confianza=0.9,
        similarity=0.8,
        geom_geojson={"type": "Point", "coordinates": [0, 0]},
        distance_to_reference_m=12.5,
        reference_id=99,
    )
    detection_repository = MagicMock()
    detection_repository.search_hybrid = AsyncMock(return_value=[])
    detection_repository.search_spatial_near = AsyncMock(return_value=[detection])
    use_case, text_embedder, _ = _build_use_case(
        structured=structured, detection_repository=detection_repository
    )

    result = asyncio.run(
        use_case.execute(
            SearchRequestDTO(
                query="coches cerca de una rotonda",
                filters=SearchFilters(top_k=10, per_layer_limit=100, min_confidence=0.0),
            )
        )
    )

    text_embedder.embed_text.assert_called_once_with("vehicle")
    meta = result.feature_collection["metadata"]
    assert meta["interpretation"]["intent"] == "search_spatial"
    assert meta["interpretation"]["embedding_text"] == "vehicle"
    assert result.feature_collection["features"][0]["properties"]["distance_to_reference_m"] == 12.5
    timings = meta["timings"]
    assert set(timings) == {"llm_ms", "clip_ms", "database_ms", "total_ms"}
    assert all(isinstance(timings[key], float) and timings[key] >= 0 for key in timings)
