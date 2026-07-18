from abc import ABC, abstractmethod

from domain.entities.detection import Detection


class DetectionRepository(ABC):
    @abstractmethod
    async def search_hybrid(
        self,
        *,
        layer_names: list[str],
        clase_yolo_list: list[str],
        query_embedding: list[float],
        per_layer_limit: int,
        min_confidence: float,
    ) -> list[Detection]:
        raise NotImplementedError
