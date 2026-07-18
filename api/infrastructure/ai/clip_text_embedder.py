"""CLIP text embeddings compatible with image embeddings from tools/embed.py."""

from __future__ import annotations

import logging
import math

import torch
from transformers import CLIPModel, CLIPProcessor

from config import settings
from domain.services.text_embedder import TextEmbedder

logger = logging.getLogger(__name__)

# Mismo modelo que embed.py (DEFAULT_MODEL).
HUGGINGFACE_CLIP_MODEL = "openai/clip-vit-base-patch32"
# Equivalente en sentence-transformers: clip-ViT-B-32


def resolve_clip_model_name() -> str:
    if settings.clip_model_name in {"clip-ViT-B-32", "openai/clip-vit-base-patch32"}:
        return HUGGINGFACE_CLIP_MODEL
    return settings.clip_model_name


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
