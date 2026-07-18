from typing import Any, Literal

from pydantic import BaseModel, Field


class StructuredQuery(BaseModel):
    intent: Literal["search_class", "search_spatial", "search_attribute", "unknown"]
    detected_language: Literal["es", "en", "unknown"]
    object_label: str | None = None
    canonical_label: str | None = None
    clase_yolo_candidates: list[str] = Field(default_factory=list)
    attributes: list[str] = Field(default_factory=list)
    reasoning: str = ""

    relation: Literal["near", "inside"] | None = None
    distance_m: float | None = None

    target_label: str | None = None
    target_canonical_label: str | None = None
    target_clase_yolo: list[str] = Field(default_factory=list)

    reference_label: str | None = None
    reference_canonical_label: str | None = None
    reference_clase_yolo: list[str] = Field(default_factory=list)

    def effective_target_classes(self) -> list[str]:
        if self.target_clase_yolo:
            return list(self.target_clase_yolo)
        return list(self.clase_yolo_candidates)

    def effective_target_canonical(self) -> str | None:
        return self.target_canonical_label or self.canonical_label

    def effective_target_label(self) -> str | None:
        return self.target_label or self.object_label

    def effective_reference_classes(self) -> list[str]:
        return list(self.reference_clase_yolo)


def build_interpretation_summary(
    structured: StructuredQuery,
    *,
    distance_m: float | None = None,
    language: str | None = None,
) -> str:
    lang = language or structured.detected_language
    target = structured.effective_target_label() or structured.effective_target_canonical() or "objeto"
    reference = (
        structured.reference_label
        or structured.reference_canonical_label
        or "referencia"
    )
    radius = distance_m if distance_m is not None else structured.distance_m

    if structured.intent == "search_spatial" and structured.relation == "near":
        if lang == "en":
            if radius is not None:
                return f"Searching for {target} within {radius:g} m of {reference}"
            return f"Searching for {target} near {reference}"
        if radius is not None:
            return f"Buscando {target} a menos de {radius:g} m de {reference}"
        return f"Buscando {target} cerca de {reference}"

    if structured.intent == "search_class":
        attrs = ", ".join(structured.attributes) if structured.attributes else ""
        if lang == "en":
            if attrs:
                return f"Searching for {attrs} {target}"
            return f"Searching for {target}"
        if attrs:
            return f"Buscando {target} ({attrs})"
        return f"Buscando {target}"

    if lang == "en":
        return "Could not interpret the query"
    return "No se pudo interpretar la consulta"


def build_interpretation(
    structured: StructuredQuery,
    *,
    embedding_text: str,
    distance_m: float | None = None,
    source: str = "llm",
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    lang = structured.detected_language
    summary_key = "summary_en" if lang == "en" else "summary_es"
    summary = build_interpretation_summary(
        structured, distance_m=distance_m, language=lang
    )

    interpretation: dict[str, Any] = {
        summary_key: summary,
        "intent": structured.intent,
        "target": {
            "label": structured.effective_target_label(),
            "canonical": structured.effective_target_canonical(),
            "clase_yolo": structured.effective_target_classes(),
        },
        "relation": structured.relation,
        "distance_m": distance_m if distance_m is not None else structured.distance_m,
        "embedding_text": embedding_text,
        "source": source,
    }

    if structured.intent == "search_spatial" or structured.reference_clase_yolo:
        interpretation["reference"] = {
            "label": structured.reference_label,
            "canonical": structured.reference_canonical_label,
            "clase_yolo": structured.effective_reference_classes(),
        }

    return interpretation
