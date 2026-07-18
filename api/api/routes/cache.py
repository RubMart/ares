from fastapi import APIRouter, HTTPException

from api import dependencies as deps
from api.schemas.search import LlmCacheClearResponse, LlmCacheStatusResponse
from infrastructure.ai.caching_query_analyzer import CachingQueryAnalyzer

router = APIRouter(tags=["cache"])


def _require_caching_analyzer() -> CachingQueryAnalyzer:
    analyzer = deps.get_services().query_analyzer
    if not isinstance(analyzer, CachingQueryAnalyzer):
        raise HTTPException(status_code=404, detail="LLM cache not available")
    return analyzer


@router.get("/cache/llm", response_model=LlmCacheStatusResponse)
async def get_llm_cache() -> LlmCacheStatusResponse:
    snapshot = await _require_caching_analyzer().snapshot()
    return LlmCacheStatusResponse(**snapshot)


@router.delete("/cache/llm", response_model=LlmCacheClearResponse)
async def clear_llm_cache() -> LlmCacheClearResponse:
    result = await _require_caching_analyzer().clear()
    return LlmCacheClearResponse(**result)
