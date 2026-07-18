from application.dto.search_dto import SearchRequestDTO, SearchResponseDTO
from domain.repositories.catalog_repository import CatalogRepository
from domain.repositories.detection_repository import DetectionRepository
from domain.services.query_analyzer import QueryAnalyzer
from domain.services.text_embedder import TextEmbedder
from infrastructure.ai.attribute_catalog import build_clip_embedding_text
from infrastructure.geo.geojson_serializer import GeoJsonSerializer


class SearchValidationError(ValueError):
    pass


class SearchDetectionsUseCase:
    def __init__(
        self,
        *,
        query_analyzer: QueryAnalyzer,
        text_embedder: TextEmbedder,
        catalog_repository: CatalogRepository,
        detection_repository: DetectionRepository,
    ) -> None:
        self._query_analyzer = query_analyzer
        self._text_embedder = text_embedder
        self._catalog_repository = catalog_repository
        self._detection_repository = detection_repository

    async def execute(self, request: SearchRequestDTO) -> SearchResponseDTO:
        query = request.query.strip()
        if not query:
            raise SearchValidationError("La consulta no puede estar vacía.")

        structured_query = await self._query_analyzer.analyze(query)

        if structured_query.intent != "search_class":
            raise SearchValidationError(
                "Solo se admiten búsquedas por clase de objeto en esta versión."
            )

        if not structured_query.clase_yolo_candidates:
            raise SearchValidationError(
                "No se pudo mapear la consulta a ninguna clase YOLO conocida."
            )

        embedding_text = build_clip_embedding_text(structured_query, query)
        query_embedding = self._text_embedder.embed_text(embedding_text)

        catalog_layers = await self._catalog_repository.list_layers()
        layer_names = [layer.nombre_capa for layer in catalog_layers]
        if not layer_names:
            raise SearchValidationError("No hay capas registradas en el catálogo.")

        detections = await self._detection_repository.search_hybrid(
            layer_names=layer_names,
            clase_yolo_list=structured_query.clase_yolo_candidates,
            query_embedding=query_embedding,
            per_layer_limit=request.filters.per_layer_limit,
            min_confidence=request.filters.min_confidence,
        )

        top_detections = detections[: request.filters.top_k]
        feature_collection = GeoJsonSerializer.to_feature_collection(
            detections=top_detections,
            query=query,
            structured_query=structured_query,
            layers_searched=layer_names,
        )

        return SearchResponseDTO(
            feature_collection=feature_collection,
            structured_query=structured_query,
        )
