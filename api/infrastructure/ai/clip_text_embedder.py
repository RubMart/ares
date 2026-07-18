"""CLIP text embeddings compatible with image embeddings from tools/embed.py."""

from __future__ import annotations

import logging
import math
from pathlib import Path

import torch
from transformers import CLIPModel, CLIPProcessor

from config import settings
from domain.services.text_embedder import TextEmbedder

logger = logging.getLogger(__name__)

# Mismo modelo que embed.py (DEFAULT_MODEL).
HUGGINGFACE_CLIP_MODEL = "openai/clip-vit-base-patch32"
# Equivalente en sentence-transformers: clip-ViT-B-32
CLIP_MODEL_ALIASES = frozenset({"clip-ViT-B-32", "openai/clip-vit-base-patch32"})

_API_ROOT = Path(__file__).resolve().parents[2]


def resolve_clip_local_dir() -> Path:
    path = Path(settings.clip_local_dir)
    if not path.is_absolute():
        path = (_API_ROOT / path).resolve()
    return path


def _is_clip_dir_ready(path: Path) -> bool:
    return path.is_dir() and (path / "config.json").is_file()


def _hf_hub_cache_root() -> Path:
    import os

    if os.environ.get("HF_HUB_CACHE"):
        return Path(os.environ["HF_HUB_CACHE"])
    if os.environ.get("HUGGINGFACE_HUB_CACHE"):
        return Path(os.environ["HUGGINGFACE_HUB_CACHE"])
    hf_home = Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface"))
    return hf_home / "hub"


def find_hf_hub_snapshot(repo_id: str) -> Path | None:
    """Busca un snapshot usable en la caché global de Hugging Face Hub."""
    cache_root = _hf_hub_cache_root()
    repo_dir = cache_root / f"models--{repo_id.replace('/', '--')}"
    if not repo_dir.is_dir():
        return None

    refs_main = repo_dir / "refs" / "main"
    if refs_main.is_file():
        revision = refs_main.read_text(encoding="utf-8").strip()
        candidate = repo_dir / "snapshots" / revision
        if _is_clip_dir_ready(candidate):
            return candidate.resolve()

    snapshots = repo_dir / "snapshots"
    if not snapshots.is_dir():
        return None
    for snapshot in sorted(snapshots.iterdir(), reverse=True):
        if _is_clip_dir_ready(snapshot):
            return snapshot.resolve()
    return None


def resolve_clip_model_name() -> str:
    """Resuelve ruta local o id HF; descarga a clip_local_dir si falta el alias canónico."""
    name = settings.clip_model_name.strip()
    as_path = Path(name)
    if _is_clip_dir_ready(as_path):
        return str(as_path.resolve())

    if name not in CLIP_MODEL_ALIASES:
        return name

    local_dir = resolve_clip_local_dir()
    if _is_clip_dir_ready(local_dir):
        logger.info("CLIP cargado desde %s", local_dir)
        return str(local_dir)

    cached = find_hf_hub_snapshot(HUGGINGFACE_CLIP_MODEL)
    if cached is not None:
        logger.info("CLIP encontrado en caché HF: %s", cached)
        return str(cached)

    logger.info(
        "CLIP no encontrado en %s ni en caché HF; descargando %s...",
        local_dir,
        HUGGINGFACE_CLIP_MODEL,
    )
    local_dir.parent.mkdir(parents=True, exist_ok=True)
    from huggingface_hub import snapshot_download

    # token=False: repos públicos no deben usar un token local inválido/caducado
    # (HF responde a veces "Repository Not Found" + OAuth signature failed).
    snapshot_download(
        repo_id=HUGGINGFACE_CLIP_MODEL,
        local_dir=str(local_dir),
        token=False,
    )
    return str(local_dir)


class ClipOnnxTextEmbedder(TextEmbedder):
    """Genera embeddings de texto en el mismo espacio CLIP que los recortes en BBDD."""

    def __init__(self) -> None:
        model_name = resolve_clip_model_name()
        self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self._processor = CLIPProcessor.from_pretrained(model_name)
        self._model = self._load_model(model_name)
        if hasattr(self._model, "eval"):
            self._model.eval()

        probe = self.embed_text("test")
        if len(probe) != settings.embedding_dim:
            raise RuntimeError(
                f"Dimensión de embedding inesperada: {len(probe)} "
                f"(esperado {settings.embedding_dim})"
            )
        logger.info("CLIP texto cargado: %s en %s", model_name, self._device)

    def _load_model(self, model_name: str) -> CLIPModel:
        if not settings.clip_onnx_backend:
            return CLIPModel.from_pretrained(model_name).to(self._device)

        try:
            from optimum.onnxruntime import ORTModelForFeatureExtraction

            model = ORTModelForFeatureExtraction.from_pretrained(
                model_name,
                export=True,
            )
            logger.info("CLIP texto usando ONNX Runtime (optimum)")
            return model  # type: ignore[return-value]
        except Exception as exc:
            logger.warning(
                "No se pudo cargar CLIP ONNX (%s). Usando PyTorch.", exc
            )
            return CLIPModel.from_pretrained(model_name).to(self._device)

    def embed_text(self, text: str) -> list[float]:
        inputs = self._processor(
            text=[text],
            return_tensors="pt",
            padding=True,
            truncation=True,
        )
        inputs = {key: value.to(self._device) for key, value in inputs.items()}

        with torch.no_grad():
            if hasattr(self._model, "get_text_features"):
                features = self._model.get_text_features(**inputs)
            else:
                text_outputs = self._model.text_model(
                    input_ids=inputs["input_ids"],
                    attention_mask=inputs.get("attention_mask"),
                )
                pooled = text_outputs.pooler_output
                features = self._model.text_projection(pooled)

            features = features / features.norm(dim=-1, keepdim=True)

        return self._normalize(features[0].cpu().tolist())

    def embedding_dimension(self) -> int:
        return settings.embedding_dim

    @staticmethod
    def _normalize(values: list[float]) -> list[float]:
        norm = math.sqrt(sum(value * value for value in values))
        if norm == 0:
            return values
        return [value / norm for value in values]
