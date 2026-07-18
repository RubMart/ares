from typing import Any

from domain.entities.detection import Detection
from domain.value_objects.semantic_query import StructuredQuery


class GeoJsonSerializer:
    @staticmethod
    def to_feature_collection(
        *,
        detections: list[Detection],
        query: str,
        structured_query: StructuredQuery,
        layers_searched: list[str],
    ) -> dict[str, Any]:
        features = [
            {
                "type": "Feature",
                "id": f"{detection.layer}/{detection.id}",
                "geometry": detection.geom_geojson,
                "properties": {
                    "layer": detection.layer,
                    "similarity": round(detection.similarity, 6),
                    "clase_yolo": detection.clase_yolo,
                    "modelo_deteccion": detection.modelo_deteccion,
                    "confianza": detection.confianza,
                    "tile_id": detection.tile_id,
                    "query": query,
                },
            }
            for detection in detections
        ]

        return {
            "type": "FeatureCollection",
            "crs": {
                "type": "name",
                "properties": {"name": "EPSG:3857"},
            },
            "features": features,
            "metadata": {
                "query": query,
                "detected_language": structured_query.detected_language,
                "structured_query": structured_query.model_dump(),
                "total_features": len(features),
                "layers_searched": layers_searched,
            },
        }
