import json

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from domain.entities.detection import Detection
from domain.repositories.detection_repository import DetectionRepository
from infrastructure.db.validators import format_pgvector_literal, validate_layer_name


class PostgresDetectionRepository(DetectionRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _row_to_detection(self, row: dict, *, spatial: bool = False) -> Detection:
        geom_raw = row["geom_json"]
        geom_geojson = json.loads(geom_raw) if geom_raw else {}
        reference_geom_geojson = None
        if spatial and row.get("reference_geom_json"):
            reference_geom_geojson = json.loads(row["reference_geom_json"])

        return Detection(
            id=row["id"],
            layer=row["layer"],
            tile_id=row["tile_id"],
            clase_yolo=row["clase_yolo"],
            modelo_deteccion=row["modelo_deteccion"],
            confianza=float(row["confianza"]),
            similarity=float(row["similarity"]),
            geom_geojson=geom_geojson,
            distance_to_reference_m=(
                float(row["distance_to_reference_m"])
                if spatial and row.get("distance_to_reference_m") is not None
                else None
            ),
            reference_id=row.get("reference_id") if spatial else None,
            reference_geom_geojson=reference_geom_geojson,
            reference_clase_yolo=row.get("reference_clase_yolo") if spatial else None,
        )

    async def search_hybrid(
        self,
        *,
        layer_names: list[str],
        clase_yolo_list: list[str],
        query_embedding: list[float],
        per_layer_limit: int,
        min_confidence: float,
    ) -> list[Detection]:
        if not layer_names or not clase_yolo_list:
            return []

        vector_literal = format_pgvector_literal(query_embedding)
        all_detections: list[Detection] = []

        for layer_name in layer_names:
            table_name = validate_layer_name(layer_name)
            query = text(
                f"""
                SELECT
                    :layer_name AS layer,
                    id,
                    tile_id,
                    clase_yolo,
                    modelo_deteccion,
                    confianza,
                    ST_AsGeoJSON(geom) AS geom_json,
                    1 - (embedding <=> CAST(:query_vec AS vector)) AS similarity
                FROM {table_name}
                WHERE clase_yolo = ANY(:clase_yolo_list)
                  AND confianza >= :min_conf
                ORDER BY embedding <=> CAST(:query_vec AS vector)
                LIMIT :per_layer_limit
                """
            )
            result = await self._session.execute(
                query,
                {
                    "layer_name": table_name,
                    "query_vec": vector_literal,
                    "clase_yolo_list": clase_yolo_list,
                    "min_conf": min_confidence,
                    "per_layer_limit": per_layer_limit,
                },
            )
            for row in result.mappings():
                all_detections.append(self._row_to_detection(dict(row), spatial=False))

        all_detections.sort(key=lambda item: item.similarity, reverse=True)
        return all_detections

    async def search_spatial_near(
        self,
        *,
        layer_names: list[str],
        target_clase_yolo_list: list[str],
        reference_clase_yolo_list: list[str],
        query_embedding: list[float],
        distance_m: float,
        per_layer_limit: int,
        min_confidence: float,
    ) -> list[Detection]:
        if (
            not layer_names
            or not target_clase_yolo_list
            or not reference_clase_yolo_list
            or distance_m <= 0
        ):
            return []

        vector_literal = format_pgvector_literal(query_embedding)
        all_detections: list[Detection] = []

        for layer_name in layer_names:
            table_name = validate_layer_name(layer_name)
            query = text(
                f"""
                SELECT
                    layer,
                    id,
                    tile_id,
                    clase_yolo,
                    modelo_deteccion,
                    confianza,
                    geom_json,
                    similarity,
                    distance_to_reference_m,
                    reference_id,
                    reference_geom_json,
                    reference_clase_yolo
                FROM (
                    SELECT DISTINCT ON (t.id)
                        :layer_name AS layer,
                        t.id,
                        t.tile_id,
                        t.clase_yolo,
                        t.modelo_deteccion,
                        t.confianza,
                        ST_AsGeoJSON(t.geom) AS geom_json,
                        1 - (t.embedding <=> CAST(:query_vec AS vector)) AS similarity,
                        ST_Distance(t.geom, r.geom) AS distance_to_reference_m,
                        r.id AS reference_id,
                        ST_AsGeoJSON(r.geom) AS reference_geom_json,
                        r.clase_yolo AS reference_clase_yolo
                    FROM {table_name} t
                    JOIN {table_name} r
                      ON r.clase_yolo = ANY(:reference_classes)
                     AND ST_DWithin(t.geom, r.geom, :distance_m)
                    WHERE t.clase_yolo = ANY(:target_classes)
                      AND t.confianza >= :min_conf
                    ORDER BY t.id, ST_Distance(t.geom, r.geom)
                ) nearest
                ORDER BY similarity DESC
                LIMIT :per_layer_limit
                """
            )
            result = await self._session.execute(
                query,
                {
                    "layer_name": table_name,
                    "query_vec": vector_literal,
                    "target_classes": target_clase_yolo_list,
                    "reference_classes": reference_clase_yolo_list,
                    "distance_m": distance_m,
                    "min_conf": min_confidence,
                    "per_layer_limit": per_layer_limit,
                },
            )
            for row in result.mappings():
                all_detections.append(self._row_to_detection(dict(row), spatial=True))

        all_detections.sort(key=lambda item: item.similarity, reverse=True)
        return all_detections
