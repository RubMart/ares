from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "detecciones-search-api"
    debug: bool = False
    cors_origins: list[str] = ["*"]

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/detecciones"

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:3b"
    ollama_temperature: float = 0.0

    clip_model_name: str = "clip-ViT-B-32"
    # Relativo a api/ → <repo>/models/clip-vit-base-patch32 (fuera de git).
    clip_local_dir: str = "../models/clip-vit-base-patch32"
    clip_onnx_backend: bool = False
    embedding_dim: int = 512

    default_top_k: int = 50
    default_per_layer_limit: int = 100
    default_min_confidence: float = 0.0

    catalog_table: str = "detecciones_catalogo"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
