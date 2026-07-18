from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import build_catalog_repository, get_db_session
from api.schemas.search import CatalogLayerResponse

router = APIRouter(tags=["catalog"])


@router.get("/catalog", response_model=list[CatalogLayerResponse])
async def list_catalog(
    session: AsyncSession = Depends(get_db_session),
) -> list[CatalogLayerResponse]:
    repository = build_catalog_repository(session)
    layers = await repository.list_layers()
    return [
        CatalogLayerResponse(
            id=layer.id,
            nombre_capa=layer.nombre_capa,
            cog_url=layer.cog_url,
            bbox=layer.bbox_geojson,
            metadata=layer.metadata,
        )
        for layer in layers
    ]
