from abc import ABC, abstractmethod

from domain.entities.catalog_layer import CatalogLayer


class CatalogRepository(ABC):
    @abstractmethod
    async def list_layers(self) -> list[CatalogLayer]:
        raise NotImplementedError
