from unittest.mock import AsyncMock, MagicMock, patch

import asyncio

import pytest
from fastapi.testclient import TestClient

from api.dependencies import AppServices
from domain.value_objects.semantic_query import StructuredQuery
from infrastructure.ai.caching_query_analyzer import CachingQueryAnalyzer, make_cache_key


@pytest.fixture
def client() -> TestClient:
    mock_services = AppServices(
        text_embedder=MagicMock(),
        query_analyzer=MagicMock(),
    )
    with patch("api.dependencies.init_services", return_value=mock_services):
        with patch("api.dependencies.get_services", return_value=mock_services):
            from main import app

            with TestClient(app) as test_client:
                yield test_client


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

            with TestClient(app) as test_client:
                yield test_client, caching


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
