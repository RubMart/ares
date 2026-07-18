import json

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from domain.entities.catalog_layer import CatalogLayer
from domain.repositories.catalog_repository import CatalogRepository


from infrastructure.db.validators import validate_layer_name


class PostgresCatalogRepository(CatalogRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._catalog_table = validate_layer_name(settings.catalog_table)

    async def list_layers(self) -> list[CatalogLayer]:
        query = text(
            f"""
            SELECT
                id,
                nombre_capa,
                cog_url,
                ST_AsGeoJSON(bbox) AS bbox_geojson,
                metadata
            FROM {self._catalog_table}
            ORDER BY nombre_capa
            """
        )
        result = await self._session.execute(query)
        layers: list[CatalogLayer] = []
        for row in result.mappings():
            bbox_raw = row["bbox_geojson"]
            bbox_geojson = json.loads(bbox_raw) if bbox_raw else None
            metadata = row["metadata"] or {}
            if not isinstance(metadata, dict):
                metadata = {}
            layers.append(
                CatalogLayer(
                    id=row["id"],
                    nombre_capa=row["nombre_capa"],
                    cog_url=row["cog_url"],
                    bbox_geojson=bbox_geojson,
                    metadata=metadata,
                )
            )
        return layers
