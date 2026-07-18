import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from application.dto.search_dto import SearchRequestDTO
from application.use_cases.search_detections import SearchDetectionsUseCase
from domain.value_objects.search_filters import SearchFilters
from domain.value_objects.semantic_query import StructuredQuery
from infrastructure.ai.caching_query_analyzer import (
    CachingQueryAnalyzer,
    make_cache_key,
    normalize_cache_query,
)


def _sample_structured(*, reasoning: str = "from-llm") -> StructuredQuery:
    return StructuredQuery(
        intent="search_class",
        detected_language="es",
        object_label="vehículos aparcados",
        canonical_label="vehicle",
        clase_yolo_candidates=["car"],
        attributes=[],
        reasoning=reasoning,
        target_canonical_label="vehicle",
        target_clase_yolo=["car"],
    )


def test_normalize_cache_query_collapses_case_and_space() -> None:
    assert normalize_cache_query("  Coches   AparCADOS ") == "coches aparcados"


def test_cache_miss_then_hit_skips_inner() -> None:
    inner = MagicMock()
    inner.analyze = AsyncMock(return_value=_sample_structured())
    caching = CachingQueryAnalyzer(inner, maxsize=8)

    async def _run() -> None:
        first = await caching.analyze("quiero ver vehículos aparcados")
        assert caching.last_hit is False
        assert inner.analyze.await_count == 1

        second = await caching.analyze("  QUIERO ver   vehículos aparcados ")
        assert caching.last_hit is True
        assert inner.analyze.await_count == 1
        assert second.canonical_label == first.canonical_label
        second.reasoning = "mutated"
        third = await caching.analyze("quiero ver vehículos aparcados")
        assert third.reasoning == "from-llm"

    asyncio.run(_run())


def test_cache_eviction_lru() -> None:
    inner = MagicMock()
    inner.analyze = AsyncMock(side_effect=lambda q: _sample_structured(reasoning=q))
    caching = CachingQueryAnalyzer(inner, maxsize=2)

    async def _run() -> None:
        await caching.analyze("query-a-ambiguous-xyz")
        await caching.analyze("query-b-ambiguous-xyz")
        await caching.analyze("query-c-ambiguous-xyz")
        assert inner.analyze.await_count == 3

        await caching.analyze("query-a-ambiguous-xyz")
        assert inner.analyze.await_count == 4
        assert caching.last_hit is False

        await caching.analyze("query-c-ambiguous-xyz")
        assert caching.last_hit is True
        assert inner.analyze.await_count == 4

    asyncio.run(_run())


def test_cache_disabled_when_maxsize_zero() -> None:
    inner = MagicMock()
    inner.analyze = AsyncMock(return_value=_sample_structured())
    caching = CachingQueryAnalyzer(inner, maxsize=0)

    async def _run() -> None:
        await caching.analyze("quiero ver vehículos aparcados")
        await caching.analyze("quiero ver vehículos aparcados")
        assert inner.analyze.await_count == 2
        assert caching.last_hit is False

    asyncio.run(_run())


def test_cache_key_includes_model(monkeypatch: pytest.MonkeyPatch) -> None:
    from config import settings

    inner = MagicMock()
    inner.analyze = AsyncMock(return_value=_sample_structured())
    caching = CachingQueryAnalyzer(inner, maxsize=8)

    async def _run() -> None:
        monkeypatch.setattr(settings, "ollama_model", "llama3.2:3b")
        await caching.analyze("quiero ver vehículos aparcados")
        assert inner.analyze.await_count == 1

        monkeypatch.setattr(settings, "ollama_model", "llama3.2:1b")
        await caching.analyze("quiero ver vehículos aparcados")
        assert inner.analyze.await_count == 2
        assert caching.last_hit is False

    asyncio.run(_run())
    assert make_cache_key("x", model="a") != make_cache_key("x", model="b")


def test_use_case_marks_source_cache_on_last_hit() -> None:
    structured = _sample_structured()
    query_analyzer = MagicMock()
    query_analyzer.analyze = AsyncMock(return_value=structured)
    query_analyzer.last_hit = True

    text_embedder = MagicMock()
    text_embedder.embed_text.return_value = [0.1, 0.2]

    catalog_repository = MagicMock()
    catalog_layer = MagicMock()
    catalog_layer.nombre_capa = "madrid_detections_example"
    catalog_repository.list_layers = AsyncMock(return_value=[catalog_layer])

    detection_repository = MagicMock()
    detection_repository.search_hybrid = AsyncMock(return_value=[])
    detection_repository.search_spatial_near = AsyncMock(return_value=[])

    use_case = SearchDetectionsUseCase(
        query_analyzer=query_analyzer,
        text_embedder=text_embedder,
        catalog_repository=catalog_repository,
        detection_repository=detection_repository,
    )

    result = asyncio.run(
        use_case.execute(
            SearchRequestDTO(
                query="quiero ver vehículos aparcados",
                filters=SearchFilters(top_k=10, per_layer_limit=100, min_confidence=0.0),
            )
        )
    )

    query_analyzer.analyze.assert_awaited_once()
    assert result.feature_collection["metadata"]["interpretation"]["source"] == "cache"


def test_snapshot_and_clear() -> None:
    inner = MagicMock()
    inner.analyze = AsyncMock(return_value=_sample_structured())
    caching = CachingQueryAnalyzer(inner, maxsize=8)

    async def _run() -> None:
        empty = await caching.snapshot()
        assert empty == {
            "size": 0,
            "maxsize": 8,
            "enabled": True,
            "keys": [],
        }

        await caching.analyze("quiero ver vehículos aparcados")
        await caching.analyze("otra consulta ambigua xyz")
        snap = await caching.snapshot()
        assert snap["size"] == 2
        assert snap["maxsize"] == 8
        assert snap["enabled"] is True
        assert snap["keys"] == [
            make_cache_key("quiero ver vehículos aparcados"),
            make_cache_key("otra consulta ambigua xyz"),
        ]

        cleared = await caching.clear()
        assert cleared == {
            "cleared": True,
            "size": 0,
            "maxsize": 8,
            "enabled": True,
        }
        after = await caching.snapshot()
        assert after["size"] == 0
        assert after["keys"] == []

        await caching.analyze("quiero ver vehículos aparcados")
        assert caching.last_hit is False
        assert inner.analyze.await_count == 3

    asyncio.run(_run())


def test_snapshot_when_disabled() -> None:
    caching = CachingQueryAnalyzer(MagicMock(), maxsize=0)

    async def _run() -> None:
        snap = await caching.snapshot()
        assert snap["enabled"] is False
        assert snap["maxsize"] == 0
        assert snap["keys"] == []

    asyncio.run(_run())
