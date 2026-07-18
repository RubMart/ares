from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CatalogLayer:
    id: int
    nombre_capa: str
    cog_url: str
    bbox_geojson: dict[str, Any] | None
    metadata: dict[str, Any]
