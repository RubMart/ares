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
    distance_to_reference_m: float | None = None
    reference_id: int | None = None
    reference_geom_geojson: dict[str, Any] | None = None
    reference_clase_yolo: str | None = None
