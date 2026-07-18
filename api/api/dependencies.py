from dataclasses import dataclass
from typing import Any

from application.use_cases.search_detections import SearchDetectionsUseCase
from config import settings
from domain.services.query_analyzer import QueryAnalyzer
from domain.services.text_embedder import TextEmbedder
from infrastructure.ai.caching_query_analyzer import CachingQueryAnalyzer
from infrastructure.ai.clip_text_embedder import ClipOnnxTextEmbedder
from infrastructure.ai.ollama_query_analyzer import OllamaQueryAnalyzer
from infrastructure.db.postgres_catalog_repository import PostgresCatalogRepository
from infrastructure.db.postgres_detection_repository import PostgresDetectionRepository
from infrastructure.db.session import async_session_factory
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class AppServices:
    text_embedder: TextEmbedder
    query_analyzer: QueryAnalyzer


_services: AppServices | None = None


def get_services() -> AppServices:
    if _services is None:
        raise RuntimeError("Los servicios de la aplicación no están inicializados.")
    return _services


def init_services() -> AppServices:
    global _services
    _services = AppServices(
        text_embedder=ClipOnnxTextEmbedder(),
        query_analyzer=CachingQueryAnalyzer(
            OllamaQueryAnalyzer(),
            maxsize=settings.llm_cache_maxsize,
        ),
    )
    return _services


def shutdown_services() -> None:
    global _services
    _services = None


async def get_db_session() -> Any:
    async with async_session_factory() as session:
        yield session


def build_search_use_case(session: AsyncSession) -> SearchDetectionsUseCase:
    services = get_services()
    return SearchDetectionsUseCase(
        query_analyzer=services.query_analyzer,
        text_embedder=services.text_embedder,
        catalog_repository=PostgresCatalogRepository(session),
        detection_repository=PostgresDetectionRepository(session),
    )


def build_catalog_repository(session: AsyncSession) -> PostgresCatalogRepository:
    return PostgresCatalogRepository(session)
