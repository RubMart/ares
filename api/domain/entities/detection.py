from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Detection:
    id: int
    layer: str
    tile_id: str
    clase_yolo: str
    modelo_deteccion: str
    confianza: float
    similarity: float
    geom_geojson: dict[str, Any]
