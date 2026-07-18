from typing import Any

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Consulta en español o inglés")
    top_k: int | None = Field(default=None, ge=1, le=500)
    per_layer_limit: int | None = Field(default=None, ge=1, le=2000)
    min_confidence: float | None = Field(default=None, ge=0.0, le=1.0)


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
