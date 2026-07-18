import httpx

from config import settings


async def check_ollama_connection() -> str:
    """Devuelve 'ok' si Ollama responde y el modelo configurado está disponible."""
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags")
            response.raise_for_status()
            models = response.json().get("models", [])
            model_names = {m.get("name", "").split(":")[0] for m in models}
            configured = settings.ollama_model.split(":")[0]
            if configured in model_names or any(
                m.get("name", "").startswith(settings.ollama_model) for m in models
            ):
                return "ok"
            return "model_missing"
    except Exception:
        return "error"
