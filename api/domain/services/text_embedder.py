from abc import ABC, abstractmethod


class TextEmbedder(ABC):
    @abstractmethod
    def embed_text(self, text: str) -> list[float]:
        raise NotImplementedError

    @abstractmethod
    def embedding_dimension(self) -> int:
        raise NotImplementedError
