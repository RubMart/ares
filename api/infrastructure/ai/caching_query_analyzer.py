from __future__ import annotations

import asyncio
import re
import unicodedata
from collections import OrderedDict

from config import settings
from domain.services.query_analyzer import QueryAnalyzer
from domain.value_objects.semantic_query import StructuredQuery


def normalize_cache_query(query: str) -> str:
    text = unicodedata.normalize("NFKC", query.strip())
    text = re.sub(r"\s+", " ", text)
    return text.casefold()


def make_cache_key(query: str, *, model: str | None = None) -> str:
    ollama_model = model if model is not None else settings.ollama_model
    return f"{ollama_model}|{normalize_cache_query(query)}"


class CachingQueryAnalyzer(QueryAnalyzer):
    """LRU in-memory cache around a QueryAnalyzer (typically Ollama)."""

    def __init__(self, inner: QueryAnalyzer, *, maxsize: int | None = None) -> None:
        self._inner = inner
        self._maxsize = settings.llm_cache_maxsize if maxsize is None else maxsize
        self._cache: OrderedDict[str, StructuredQuery] = OrderedDict()
        self._lock = asyncio.Lock()
        self.last_hit: bool = False

    async def analyze(self, query: str) -> StructuredQuery:
        if self._maxsize <= 0:
            self.last_hit = False
            return await self._inner.analyze(query)

        key = make_cache_key(query)

        async with self._lock:
            cached = self._cache.get(key)
            if cached is not None:
                self._cache.move_to_end(key)
                self.last_hit = True
                return cached.model_copy(deep=True)

        structured = await self._inner.analyze(query)

        async with self._lock:
            # Another coroutine may have filled the same key while we awaited.
            existing = self._cache.get(key)
            if existing is not None:
                self._cache.move_to_end(key)
                self.last_hit = True
                return existing.model_copy(deep=True)

            self._cache[key] = structured.model_copy(deep=True)
            self._cache.move_to_end(key)
            while len(self._cache) > self._maxsize:
                self._cache.popitem(last=False)
            self.last_hit = False
            return structured.model_copy(deep=True)

    async def snapshot(self) -> dict[str, object]:
        async with self._lock:
            return {
                "size": len(self._cache),
                "maxsize": self._maxsize,
                "enabled": self._maxsize > 0,
                "keys": list(self._cache.keys()),
            }

    async def clear(self) -> dict[str, object]:
        async with self._lock:
            self._cache.clear()
            return {
                "cleared": True,
                "size": 0,
                "maxsize": self._maxsize,
                "enabled": self._maxsize > 0,
            }
