import os

import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DB_INTEGRATION", "").lower() not in {"1", "true", "yes"},
    reason="Definir RUN_DB_INTEGRATION=1 y PostgreSQL con sql_test cargado",
)


@pytest.mark.asyncio
async def test_catalog_layers_when_db_available() -> None:
    from infrastructure.db.postgres_catalog_repository import PostgresCatalogRepository
    from infrastructure.db.session import async_session_factory

    async with async_session_factory() as session:
        repository = PostgresCatalogRepository(session)
        layers = await repository.list_layers()
        assert isinstance(layers, list)
