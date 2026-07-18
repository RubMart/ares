import asyncio
from unittest.mock import AsyncMock, MagicMock

from application.dto.search_dto import SearchRequestDTO
from application.use_cases.search_detections import SearchDetectionsUseCase
from domain.value_objects.search_filters import SearchFilters
from domain.value_objects.semantic_query import StructuredQuery


def test_search_uses_attribute_enriched_embedding_text() -> None:
    structured = StructuredQuery(
        intent="search_class",
        detected_language="es",
        object_label="coches rojos",
        canonical_label="vehicle",
        clase_yolo_candidates=["car", "small vehicle"],
        attributes=["red"],
        reasoning="",
    )

    query_analyzer = MagicMock()
    query_analyzer.analyze = AsyncMock(return_value=structured)

    text_embedder = MagicMock()
    text_embedder.embed_text.return_value = [0.1, 0.2]

    catalog_repository = MagicMock()
    catalog_layer = MagicMock()
    catalog_layer.nombre_capa = "madrid_detections_example"
    catalog_repository.list_layers = AsyncMock(return_value=[catalog_layer])

    detection_repository = MagicMock()
    detection_repository.search_hybrid = AsyncMock(return_value=[])

    use_case = SearchDetectionsUseCase(
        query_analyzer=query_analyzer,
        text_embedder=text_embedder,
        catalog_repository=catalog_repository,
        detection_repository=detection_repository,
    )

    asyncio.run(
        use_case.execute(
            SearchRequestDTO(
                query="coches rojos",
                filters=SearchFilters(top_k=10, per_layer_limit=100, min_confidence=0.25),
            )
        )
    )

    text_embedder.embed_text.assert_called_once_with("red vehicle")
