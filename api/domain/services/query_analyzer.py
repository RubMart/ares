from abc import ABC, abstractmethod

from domain.value_objects.semantic_query import StructuredQuery


class QueryAnalyzerError(Exception):
    """Fallo al invocar el analizador semántico (p. ej. Ollama no disponible)."""


class QueryAnalyzer(ABC):
    @abstractmethod
    async def analyze(self, query: str) -> StructuredQuery:
        raise NotImplementedError
