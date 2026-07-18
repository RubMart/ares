import json

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from domain.entities.detection import Detection
from domain.repositories.detection_repository import DetectionRepository
from infrastructure.db.validators import format_pgvector_literal, validate_layer_name


class PostgresDetectionRepository(DetectionRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

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
                geom_raw = row["geom_json"]
                geom_geojson = json.loads(geom_raw) if geom_raw else {}
                all_detections.append(
                    Detection(
                        id=row["id"],
                        layer=row["layer"],
                        tile_id=row["tile_id"],
                        clase_yolo=row["clase_yolo"],
                        modelo_deteccion=row["modelo_deteccion"],
                        confianza=float(row["confianza"]),
                        similarity=float(row["similarity"]),
                        geom_geojson=geom_geojson,
                    )
                )

        all_detections.sort(key=lambda item: item.similarity, reverse=True)
        return all_detections
