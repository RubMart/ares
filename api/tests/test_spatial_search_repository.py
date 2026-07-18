import inspect

from domain.repositories.detection_repository import DetectionRepository
from infrastructure.db.postgres_detection_repository import PostgresDetectionRepository


def test_detection_repository_declares_spatial_near() -> None:
    assert hasattr(DetectionRepository, "search_spatial_near")
    assert hasattr(PostgresDetectionRepository, "search_spatial_near")
    source = inspect.getsource(PostgresDetectionRepository.search_spatial_near)
    assert "ST_DWithin" in source
    assert "distance_to_reference_m" in source
