from fastapi import APIRouter

from api.schemas.search import HealthResponse
from config import settings
from infrastructure.ai.ollama_health import check_ollama_connection
from infrastructure.db.session import check_database_connection

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    db_status = "ok"
    try:
        await check_database_connection()
    except Exception:
        db_status = "error"

    llm_status = await check_ollama_connection()

    overall = "ok"
    if db_status != "ok" or llm_status != "ok":
        overall = "degraded"

    return HealthResponse(
        status=overall,
        database=db_status,
        llm_model=settings.ollama_model,
        llm_status=llm_status,
        clip_model=settings.clip_model_name,
        embedding_dim=settings.embedding_dim,
    )
