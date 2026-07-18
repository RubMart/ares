from unittest.mock import AsyncMock, MagicMock, patch

import asyncio

import pytest
from fastapi.testclient import TestClient

from api.dependencies import AppServices, get_db_session
from application.dto.search_dto import SearchResponseDTO
from domain.services.query_analyzer import QueryAnalyzerError
from domain.value_objects.semantic_query import StructuredQuery
from infrastructure.ai.caching_query_analyzer import CachingQueryAnalyzer, make_cache_key


async def _fake_db_session():
    yield MagicMock()


@pytest.fixture
def client() -> TestClient:
    mock_services = AppServices(
        text_embedder=MagicMock(),
        query_analyzer=MagicMock(),
    )
    with patch("api.dependencies.init_services", return_value=mock_services):
        with patch("api.dependencies.get_services", return_value=mock_services):
            from main import app

            app.state.limiter.enabled = False
            with TestClient(app) as test_client:
                yield test_client
            app.state.limiter.enabled = True


@pytest.fixture
def cache_client():
    inner = MagicMock()
    inner.analyze = AsyncMock(
        return_value=StructuredQuery(
            intent="search_class",
            detected_language="es",
            object_label="vehículos",
            canonical_label="vehicle",
            clase_yolo_candidates=["car"],
            attributes=[],
            reasoning="from-llm",
            target_canonical_label="vehicle",
            target_clase_yolo=["car"],
        )
    )
    caching = CachingQueryAnalyzer(inner, maxsize=8)
    services = AppServices(text_embedder=MagicMock(), query_analyzer=caching)
    with patch("api.dependencies.init_services", return_value=services):
        with patch("api.dependencies.get_services", return_value=services):
            from main import app

            app.state.limiter.enabled = False
            with TestClient(app) as test_client:
                yield test_client, caching
            app.state.limiter.enabled = True


def _ok_search_response() -> SearchResponseDTO:
    return SearchResponseDTO(
        feature_collection={"type": "FeatureCollection", "features": []},
        structured_query=StructuredQuery(
            intent="search_class",
            detected_language="es",
            object_label="piscinas",
            canonical_label="swimming-pool",
            clase_yolo_candidates=["swimming-pool"],
            attributes=[],
            reasoning="ok",
        ),
    )


def test_health_endpoint(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert "status" in payload
    assert payload["embedding_dim"] == 512


def test_llm_cache_not_available_with_mock_analyzer(client: TestClient) -> None:
    response = client.get("/cache/llm")
    assert response.status_code == 404
    assert response.json()["detail"] == "LLM cache not available"

    response = client.delete("/cache/llm")
    assert response.status_code == 404


def test_llm_cache_get_and_clear(cache_client) -> None:
    client, caching = cache_client

    empty = client.get("/cache/llm")
    assert empty.status_code == 200
    assert empty.json() == {
        "size": 0,
        "maxsize": 8,
        "enabled": True,
        "keys": [],
    }

    asyncio.run(caching.analyze("quiero ver vehículos aparcados"))

    status = client.get("/cache/llm")
    assert status.status_code == 200
    payload = status.json()
    assert payload["size"] == 1
    assert payload["keys"] == [make_cache_key("quiero ver vehículos aparcados")]

    cleared = client.delete("/cache/llm")
    assert cleared.status_code == 200
    assert cleared.json() == {
        "cleared": True,
        "size": 0,
        "maxsize": 8,
        "enabled": True,
    }

    after = client.get("/cache/llm")
    assert after.json()["size"] == 0
    assert after.json()["keys"] == []


def test_search_500_does_not_leak_exception_detail(client: TestClient) -> None:
    from main import app

    use_case = MagicMock()
    use_case.execute = AsyncMock(side_effect=RuntimeError("secret db detail"))

    app.dependency_overrides[get_db_session] = _fake_db_session
    try:
        with patch(
            "api.routes.search.build_search_use_case",
            return_value=use_case,
        ):
            response = client.post("/search", json={"query": "piscinas"})
    finally:
        app.dependency_overrides.pop(get_db_session, None)

    assert response.status_code == 500
    detail = response.json()["detail"]
    assert detail == "Error interno durante la búsqueda"
    assert "secret db detail" not in detail


def test_search_503_does_not_leak_exception_detail(client: TestClient) -> None:
    from main import app

    use_case = MagicMock()
    use_case.execute = AsyncMock(
        side_effect=QueryAnalyzerError("ollama timeout xyz")
    )

    app.dependency_overrides[get_db_session] = _fake_db_session
    try:
        with patch(
            "api.routes.search.build_search_use_case",
            return_value=use_case,
        ):
            response = client.post("/search", json={"query": "piscinas"})
    finally:
        app.dependency_overrides.pop(get_db_session, None)

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail == "El analizador semántico no está disponible"
    assert "ollama timeout xyz" not in detail


def test_search_rate_limit_returns_429() -> None:
    mock_services = AppServices(
        text_embedder=MagicMock(),
        query_analyzer=MagicMock(),
    )
    use_case = MagicMock()
    use_case.execute = AsyncMock(return_value=_ok_search_response())

    with patch("api.dependencies.init_services", return_value=mock_services):
        with patch("api.dependencies.get_services", return_value=mock_services):
            with patch("config.settings.rate_limit_search", "1/minute"):
                from main import app

                app.state.limiter.enabled = True
                app.state.limiter.reset()
                app.dependency_overrides[get_db_session] = _fake_db_session
                try:
                    with patch(
                        "api.routes.search.build_search_use_case",
                        return_value=use_case,
                    ):
                        with TestClient(app) as test_client:
                            first = test_client.post(
                                "/search", json={"query": "piscinas"}
                            )
                            second = test_client.post(
                                "/search", json={"query": "piscinas"}
                            )
                finally:
                    app.dependency_overrides.pop(get_db_session, None)
                    app.state.limiter.reset()
                    app.state.limiter.enabled = False

    assert first.status_code == 200
    assert second.status_code == 429
    assert "Rate limit exceeded" in second.json()["detail"]
