"""Rate limiting compartido (slowapi) para la API."""

from slowapi import Limiter
from slowapi.util import get_remote_address

from config import settings

limiter = Limiter(
    key_func=get_remote_address,
    enabled=settings.rate_limit_enabled,
)


def search_rate_limit(*_args, **_kwargs) -> str:
    """Límite dinámico leído desde settings (permite monkeypatch en tests)."""
    return settings.rate_limit_search
