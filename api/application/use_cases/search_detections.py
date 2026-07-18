import time

from application.dto.search_dto import SearchRequestDTO, SearchResponseDTO
from config import settings
from domain.repositories.catalog_repository import CatalogRepository
from domain.repositories.detection_repository import DetectionRepository
from domain.services.query_analyzer import QueryAnalyzer
from domain.services.text_embedder import TextEmbedder
from domain.value_objects.semantic_query import StructuredQuery
from infrastructure.ai.attribute_catalog import build_clip_embedding_text
from infrastructure.ai.yolo_class_catalog import find_catalog_entry
from infrastructure.geo.geojson_serializer import GeoJsonSerializer


def _elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 2)


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

    def _apply_request_overrides(
        self, structured: StructuredQuery, request: SearchRequestDTO
    ) -> tuple[StructuredQuery, list[str], str]:
        warnings: list[str] = []
        source = "llm"
        updates: dict[str, object] = {}
        filters = request.filters

        if filters.target:
            entry = find_catalog_entry(filters.target)
            if entry is None:
                raise SearchValidationError(
                    f"No se pudo mapear el target '{filters.target}' a ninguna clase YOLO conocida."
                )
            updates.update(
                {
                    "target_label": filters.target,
                    "target_canonical_label": entry.canonical_label,
                    "target_clase_yolo": list(entry.clase_yolo),
                    "canonical_label": entry.canonical_label,
                    "object_label": filters.target,
                    "clase_yolo_candidates": list(entry.clase_yolo),
                }
            )
            source = "override"

        if filters.reference:
            entry = find_catalog_entry(filters.reference)
            if entry is None:
                raise SearchValidationError(
                    f"No se pudo mapear la referencia '{filters.reference}' a ninguna clase YOLO conocida."
                )
            updates.update(
                {
                    "reference_label": filters.reference,
                    "reference_canonical_label": entry.canonical_label,
                    "reference_clase_yolo": list(entry.clase_yolo),
                    "intent": "search_spatial",
                    "relation": filters.spatial_relation or structured.relation or "near",
                }
            )
            source = "override"

        if filters.spatial_relation:
            updates["relation"] = filters.spatial_relation
            updates["intent"] = "search_spatial"
            source = "override"

        if filters.spatial_distance_m is not None:
            updates["distance_m"] = filters.spatial_distance_m
            source = "override" if source == "override" else "override"

        if updates:
            structured = structured.model_copy(update=updates)
            if source == "override":
                warnings.append("Se aplicaron parámetros explícitos de la petición.")

        return structured, warnings, source

    def _resolve_distance_m(self, structured: StructuredQuery, request: SearchRequestDTO) -> float:
        raw = (
            request.filters.spatial_distance_m
            if request.filters.spatial_distance_m is not None
            else structured.distance_m
        )
        if raw is None:
            return settings.default_spatial_distance_m

        distance = float(raw)
        if distance <= 0:
            raise SearchValidationError("spatial_distance_m debe ser mayor que 0.")
        if distance > settings.max_spatial_distance_m:
            raise SearchValidationError(
                f"spatial_distance_m no puede superar {settings.max_spatial_distance_m:g} m."
            )
        return distance

    async def execute(self, request: SearchRequestDTO) -> SearchResponseDTO:
        total_started = time.perf_counter()
        query = request.query.strip()
        if not query:
            raise SearchValidationError("La consulta no puede estar vacía.")

        llm_started = time.perf_counter()
        structured_query = await self._query_analyzer.analyze(query)
        llm_ms = _elapsed_ms(llm_started)

        structured_query, warnings, source = self._apply_request_overrides(
            structured_query, request
        )

        if structured_query.relation == "inside":
            raise SearchValidationError(
                "La relación 'inside' aún no está soportada; use 'cerca de'."
            )

        if structured_query.intent == "search_attribute":
            raise SearchValidationError(
                "Solo se admiten búsquedas por clase o relación espacial. "
                "Indica un tipo de objeto (ej. 'coches rojos')."
            )

        if structured_query.intent == "unknown":
            raise SearchValidationError(
                "No se pudo interpretar la consulta. Prueba con una clase "
                "(ej. 'piscinas') o una relación espacial (ej. 'coches cerca de rotonda')."
            )

        if structured_query.intent not in ("search_class", "search_spatial"):
            raise SearchValidationError(
                "Solo se admiten búsquedas por clase de objeto o relación espacial."
            )

        target_classes = structured_query.effective_target_classes()
        if not target_classes:
            raise SearchValidationError(
                "No se pudo mapear la consulta a ninguna clase YOLO conocida."
            )

        distance_m: float | None = None
        if structured_query.intent == "search_spatial":
            reference_classes = structured_query.effective_reference_classes()
            if not reference_classes:
                raise SearchValidationError(
                    "No se identificó objeto de referencia espacial (ej. rotonda, edificio)."
                )
            if structured_query.relation not in (None, "near"):
                raise SearchValidationError(
                    f"La relación '{structured_query.relation}' no está soportada; use 'cerca de'."
                )
            distance_m = self._resolve_distance_m(structured_query, request)
            structured_query = structured_query.model_copy(
                update={"relation": "near", "distance_m": distance_m}
            )

        embedding_text = build_clip_embedding_text(structured_query, query)
        if not embedding_text:
            raise SearchValidationError("No se pudo construir el texto de embedding CLIP.")

        clip_started = time.perf_counter()
        query_embedding = self._text_embedder.embed_text(embedding_text)
        clip_ms = _elapsed_ms(clip_started)

        db_started = time.perf_counter()
        catalog_layers = await self._catalog_repository.list_layers()
        layer_names = [layer.nombre_capa for layer in catalog_layers]
        if not layer_names:
            raise SearchValidationError("No hay capas registradas en el catálogo.")

        if structured_query.intent == "search_spatial":
            detections = await self._detection_repository.search_spatial_near(
                layer_names=layer_names,
                target_clase_yolo_list=target_classes,
                reference_clase_yolo_list=structured_query.effective_reference_classes(),
                query_embedding=query_embedding,
                distance_m=distance_m or settings.default_spatial_distance_m,
                per_layer_limit=request.filters.per_layer_limit,
                min_confidence=request.filters.min_confidence,
            )
        else:
            detections = await self._detection_repository.search_hybrid(
                layer_names=layer_names,
                clase_yolo_list=target_classes,
                query_embedding=query_embedding,
                per_layer_limit=request.filters.per_layer_limit,
                min_confidence=request.filters.min_confidence,
            )
        database_ms = _elapsed_ms(db_started)

        top_detections = detections[: request.filters.top_k]
        timings = {
            "llm_ms": llm_ms,
            "clip_ms": clip_ms,
            "database_ms": database_ms,
            "total_ms": _elapsed_ms(total_started),
        }
        feature_collection = GeoJsonSerializer.to_feature_collection(
            detections=top_detections,
            query=query,
            structured_query=structured_query,
            layers_searched=layer_names,
            embedding_text=embedding_text,
            distance_m=distance_m,
            interpretation_source=source,
            warnings=warnings,
            timings=timings,
        )

        return SearchResponseDTO(
            feature_collection=feature_collection,
            structured_query=structured_query,
        )
