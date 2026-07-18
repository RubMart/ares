from typing import Any

from domain.entities.detection import Detection
from domain.value_objects.semantic_query import StructuredQuery, build_interpretation


class GeoJsonSerializer:
    @staticmethod
    def _feature_properties(detection: Detection, query: str) -> dict[str, Any]:
        props: dict[str, Any] = {
            "layer": detection.layer,
            "similarity": round(detection.similarity, 6),
            "clase_yolo": detection.clase_yolo,
            "modelo_deteccion": detection.modelo_deteccion,
            "confianza": detection.confianza,
            "tile_id": detection.tile_id,
            "query": query,
        }
        if detection.distance_to_reference_m is not None:
            props["distance_to_reference_m"] = round(detection.distance_to_reference_m, 3)
        if detection.reference_id is not None:
            props["reference_id"] = detection.reference_id
        return props

    @staticmethod
    def _reference_features(detections: list[Detection]) -> list[dict[str, Any]]:
        seen: set[tuple[str, int]] = set()
        features: list[dict[str, Any]] = []
        for detection in detections:
            if detection.reference_id is None or not detection.reference_geom_geojson:
                continue
            key = (detection.layer, detection.reference_id)
            if key in seen:
                continue
            seen.add(key)
            features.append(
                {
                    "type": "Feature",
                    "id": f"{detection.layer}/ref/{detection.reference_id}",
                    "geometry": detection.reference_geom_geojson,
                    "properties": {
                        "layer": detection.layer,
                        "role": "reference",
                        "clase_yolo": detection.reference_clase_yolo,
                        "reference_id": detection.reference_id,
                    },
                }
            )
        return features

    @staticmethod
    def to_feature_collection(
        *,
        detections: list[Detection],
        query: str,
        structured_query: StructuredQuery,
        layers_searched: list[str],
        embedding_text: str = "",
        distance_m: float | None = None,
        interpretation_source: str = "llm",
        warnings: list[str] | None = None,
        timings: dict[str, float] | None = None,
    ) -> dict[str, Any]:
        features = [
            {
                "type": "Feature",
                "id": f"{detection.layer}/{detection.id}",
                "geometry": detection.geom_geojson,
                "properties": GeoJsonSerializer._feature_properties(detection, query),
            }
            for detection in detections
        ]

        interpretation = build_interpretation(
            structured_query,
            embedding_text=embedding_text
            or structured_query.effective_target_canonical()
            or query,
            distance_m=distance_m,
            source=interpretation_source,
            warnings=warnings,
        )
        reference_features = GeoJsonSerializer._reference_features(detections)

        metadata: dict[str, Any] = {
            "query": query,
            "detected_language": structured_query.detected_language,
            "interpretation": interpretation,
            "structured_query": structured_query.model_dump(),
            "total_features": len(features),
            "layers_searched": layers_searched,
            "warnings": warnings or [],
        }
        if timings is not None:
            metadata["timings"] = timings
        if reference_features:
            metadata["reference_features"] = {
                "type": "FeatureCollection",
                "features": reference_features,
            }

        return {
            "type": "FeatureCollection",
            "crs": {
                "type": "name",
                "properties": {"name": "EPSG:3857"},
            },
            "features": features,
            "metadata": metadata,
        }
