import unicodedata

from domain.value_objects.semantic_query import StructuredQuery

COLOR_SYNONYMS: dict[str, str] = {
    "rojo": "red",
    "rojos": "red",
    "roja": "red",
    "rojas": "red",
    "azul": "blue",
    "azules": "blue",
    "verde": "green",
    "verdes": "green",
    "negro": "black",
    "negros": "black",
    "negra": "black",
    "negras": "black",
    "blanco": "white",
    "blancos": "white",
    "blanca": "white",
    "blancas": "white",
    "amarillo": "yellow",
    "amarillos": "yellow",
    "amarilla": "yellow",
    "amarillas": "yellow",
    "gris": "gray",
    "grises": "gray",
    "naranja": "orange",
    "naranjas": "orange",
    "red": "red",
    "blue": "blue",
    "green": "green",
    "black": "black",
    "white": "white",
    "yellow": "yellow",
    "gray": "gray",
    "grey": "gray",
    "orange": "orange",
}


def _normalize_token(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.strip().lower())
    return "".join(char for char in normalized if not unicodedata.combining(char))


def normalize_attributes(attributes: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for attribute in attributes:
        token = _normalize_token(attribute)
        if not token:
            continue
        canonical = COLOR_SYNONYMS.get(token, token)
        if canonical not in seen:
            seen.add(canonical)
            normalized.append(canonical)
    return normalized


def extract_attributes_from_query(query: str) -> list[str]:
    tokens = [_normalize_token(token) for token in query.split()]
    extracted: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        if not token:
            continue
        canonical = COLOR_SYNONYMS.get(token)
        if canonical is None or canonical in seen:
            continue
        seen.add(canonical)
        extracted.append(canonical)
    return extracted


def build_clip_embedding_text(structured: StructuredQuery, original_query: str) -> str:
    attributes = normalize_attributes(structured.attributes)
    if not attributes:
        return original_query.strip()

    label = (structured.canonical_label or structured.object_label or "").strip()
    if not label:
        return original_query.strip()

    return f"{' '.join(attributes)} {label}"
