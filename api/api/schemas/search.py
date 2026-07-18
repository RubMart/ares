from typing import Any, Literal

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Consulta en español o inglés")
    top_k: int | None = Field(default=None, ge=1, le=500)
    per_layer_limit: int | None = Field(default=None, ge=1, le=2000)
    min_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    spatial_relation: Literal["near"] | None = Field(
        default=None,
        description="Override de relación espacial (v1: near)",
    )
    target: str | None = Field(
        default=None,
        description="Override del objeto buscado (canonical o sinónimo ES/EN)",
    )
    reference: str | None = Field(
        default=None,
        description="Override del objeto de referencia espacial",
    )
    spatial_distance_m: float | None = Field(
        default=None,
        ge=1,
        le=500,
        description="Radio de proximidad en metros (EPSG:3857 ~m)",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"query": "coches cerca de rotonda"},
                {
                    "query": "coches cerca de rotonda",
                    "target": "vehicle",
                    "reference": "roundabout",
                    "spatial_distance_m": 30,
                },
                {"query": "piscinas"},
            ]
        }
    }


class CatalogLayerResponse(BaseModel):
    id: int
    nombre_capa: str
    cog_url: str
    bbox: dict[str, Any] | None
    metadata: dict[str, Any]


class HealthResponse(BaseModel):
    status: str
    database: str
    llm_model: str
    llm_status: str
    clip_model: str
    embedding_dim: int


class LlmCacheStatusResponse(BaseModel):
    size: int
    maxsize: int
    enabled: bool
    keys: list[str]


class LlmCacheClearResponse(BaseModel):
    cleared: bool
    size: int
    maxsize: int
    enabled: bool
