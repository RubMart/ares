from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.dependencies import AppServices


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


def test_health_endpoint(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert "status" in payload
    assert payload["embedding_dim"] == 512
