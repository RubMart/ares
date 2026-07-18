from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import build_search_use_case, get_db_session
from api.schemas.search import SearchRequest
from application.dto.search_dto import SearchRequestDTO
from application.use_cases.search_detections import SearchValidationError
from config import settings
from domain.services.query_analyzer import QueryAnalyzerError
from domain.value_objects.search_filters import SearchFilters

router = APIRouter(tags=["search"])


@router.post("/search")
async def search_detections(
    body: SearchRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    use_case = build_search_use_case(session)
    filters = SearchFilters(
        top_k=body.top_k or settings.default_top_k,
        per_layer_limit=body.per_layer_limit or settings.default_per_layer_limit,
        min_confidence=(
            body.min_confidence
            if body.min_confidence is not None
            else settings.default_min_confidence
        ),
    )
    request = SearchRequestDTO(query=body.query, filters=filters)

    try:
        result = await use_case.execute(request)
    except SearchValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except QueryAnalyzerError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"El analizador semántico no está disponible: {exc}",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Error interno durante la búsqueda: {exc}",
        ) from exc

    return result.feature_collection
