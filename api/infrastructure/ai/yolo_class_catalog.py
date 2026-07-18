from dataclasses import dataclass
import re
import unicodedata

from domain.value_objects.semantic_query import StructuredQuery
from infrastructure.ai.attribute_catalog import (
    COLOR_SYNONYMS,
    extract_attributes_from_query,
    normalize_attributes,
)
from infrastructure.ai.spatial_query_parser import (
    merge_spatial_parse_into_structured,
    parse_spatial_relation,
)

STOP_WORDS = {
    "buscar",
    "encontrar",
    "ver",
    "mostrar",
    "quiero",
    "localizar",
    "dame",
    "lista",
    "find",
    "search",
    "show",
    "get",
    "de",
    "del",
    "la",
    "las",
    "el",
    "los",
    "en",
    "con",
    "sin",
    "y",
    "o",
    "una",
    "un",
    "unos",
    "unas",
    "the",
    "a",
    "an",
}

# Spatial relation tokens are NOT stripped during class matching of full
# compound queries; they are handled by spatial_query_parser instead.
SPATIAL_STOP_WORDS = {
    "near",
    "cerca",
    "junto",
    "alrededor",
    "next",
    "close",
    "around",
    "to",
}


@dataclass(frozen=True)
class YoloClassEntry:
    canonical_label: str
    clase_yolo: list[str]
    synonyms_es: list[str]
    synonyms_en: list[str]


YOLO_CLASS_CATALOG: list[YoloClassEntry] = [
    YoloClassEntry(
        canonical_label="swimming pool",
        clase_yolo=["swimming_pool", "swimming pool"],
        synonyms_es=["piscina", "piscinas", "alberca", "albercas"],
        synonyms_en=["pool", "pools", "swimming pool", "swimming pools"],
    ),
    YoloClassEntry(
        canonical_label="vehicle",
        clase_yolo=[
            "car",
            "small vehicle",
            "large vehicle",
            "van",
            "truck",
            "bus",
            "motor",
        ],
        synonyms_es=[
            "coche",
            "coches",
            "automovil",
            "automóvil",
            "vehiculo",
            "vehículo",
            "vehiculos",
            "vehículos",
            "furgoneta",
            "camion",
            "camión",
            "autobus",
            "autobús",
            "autobuses",
        ],
        synonyms_en=[
            "car",
            "cars",
            "vehicle",
            "vehicles",
            "van",
            "vans",
            "truck",
            "trucks",
            "bus",
            "buses",
            "motor",
        ],
    ),
    YoloClassEntry(
        canonical_label="building",
        clase_yolo=["Building", "building"],
        synonyms_es=["edificio", "edificios", "construccion", "construcción"],
        synonyms_en=["building", "buildings"],
    ),
    YoloClassEntry(
        canonical_label="photovoltaic panel",
        clase_yolo=["photovoltaic panel"],
        synonyms_es=[
            "panel solar",
            "paneles solares",
            "placa solar",
            "placas solares",
            "fotovoltaico",
            "fotovoltaicos",
            "fotovoltaica",
            "fotovoltaicas",
            "granja solar",
            "granjas solares",
        ],
        synonyms_en=[
            "solar panel",
            "solar panels",
            "photovoltaic",
            "solar farm",
        ],
    ),
    YoloClassEntry(
        canonical_label="sports field",
        clase_yolo=["soccer ball field", "basketball court"],
        synonyms_es=[
            "campo de futbol",
            "campo de fútbol",
            "campos de futbol",
            "campos de fútbol",
            "campo deportivo",
            "campos deportivos",
            "pista de baloncesto",
            "pistas de baloncesto",
            "campo de baloncesto",
            "campos de baloncesto",
        ],
        synonyms_en=[
            "soccer field",
            "football field",
            "sports field",
            "basketball court",
        ],
    ),
    YoloClassEntry(
        canonical_label="pedestrian",
        clase_yolo=["pedestrian"],
        synonyms_es=[
            "peaton",
            "peatón",
            "peatones",
            "persona",
            "personas",
            "gente",
        ],
        synonyms_en=[
            "pedestrian",
            "pedestrians",
            "person",
            "people",
            "persons",
        ],
    ),
    YoloClassEntry(
        canonical_label="roundabout",
        clase_yolo=["roundabout"],
        synonyms_es=["rotonda", "rotondas", "glorieta", "glorietas"],
        synonyms_en=["roundabout", "roundabouts", "traffic circle"],
    ),
]


def _normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.strip().lower())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    normalized = re.sub(r"[^\w\s]", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def _token_variants(token: str) -> set[str]:
    variants = {token}
    if len(token) < 3:
        return variants

    if token.endswith("es") and len(token) > 4:
        variants.add(token[:-2])
        variants.add(token[:-1])
    if token.endswith("s") and not token.endswith("ss"):
        variants.add(token[:-1])
    if not token.endswith("s"):
        variants.add(f"{token}s")
        if token[-1] in "aeiou":
            variants.add(f"{token}es")

    return {variant for variant in variants if len(variant) >= 3}


def _expand_tokens(tokens: list[str]) -> set[str]:
    expanded: set[str] = set()
    for token in tokens:
        expanded.update(_token_variants(token))
    return expanded


def _entry_terms(entry: YoloClassEntry) -> list[str]:
    return [entry.canonical_label, *entry.synonyms_es, *entry.synonyms_en]


def _all_catalog_terms() -> list[tuple[YoloClassEntry, str]]:
    terms: list[tuple[YoloClassEntry, str]] = []
    for entry in YOLO_CLASS_CATALOG:
        for term in _entry_terms(entry):
            normalized_term = _normalize_text(term)
            if normalized_term:
                terms.append((entry, normalized_term))
    terms.sort(key=lambda item: len(item[1]), reverse=True)
    return terms


def _strip_non_class_tokens(normalized: str) -> str:
    skip_tokens = STOP_WORDS | set(COLOR_SYNONYMS.keys())
    tokens = [token for token in normalized.split() if token not in skip_tokens]
    return " ".join(tokens)


def _match_exact(normalized: str) -> YoloClassEntry | None:
    for entry, term in _all_catalog_terms():
        if term == normalized:
            return entry
    return None


def _match_by_substring(normalized: str) -> YoloClassEntry | None:
    for entry, term in _all_catalog_terms():
        if term in normalized or normalized in term:
            return entry
    return None


def _match_by_token_overlap(normalized: str) -> YoloClassEntry | None:
    query_tokens = _expand_tokens(normalized.split())
    best: tuple[int, int, YoloClassEntry] | None = None

    for entry in YOLO_CLASS_CATALOG:
        for term in _entry_terms(entry):
            term_tokens = _expand_tokens(_normalize_text(term).split())
            if not term_tokens:
                continue
            overlap = len(term_tokens & query_tokens)
            if overlap == 0 or overlap < len(term_tokens):
                continue
            score = (overlap, len(term_tokens))
            if best is None or score > (best[0], best[1]):
                best = (overlap, len(term_tokens), entry)

    return best[2] if best else None


def _match_by_tokens(normalized: str) -> YoloClassEntry | None:
    term_index: dict[str, YoloClassEntry] = {}
    for entry in YOLO_CLASS_CATALOG:
        for term in _entry_terms(entry):
            term_index[_normalize_text(term)] = entry

    for token in _expand_tokens(normalized.split()):
        if token in term_index:
            return term_index[token]

    return None


def find_catalog_entry(query_or_label: str) -> YoloClassEntry | None:
    normalized = _normalize_text(query_or_label)
    if not normalized:
        return None

    for matcher in (
        _match_exact,
        _match_by_substring,
        _match_by_token_overlap,
        _match_by_tokens,
    ):
        entry = matcher(normalized)
        if entry is not None:
            return entry

    cleaned = _strip_non_class_tokens(normalized)
    if cleaned and cleaned != normalized:
        return find_catalog_entry(cleaned)

    return None


def find_catalog_entry_exact(query_or_label: str) -> YoloClassEntry | None:
    """Strict catalog match for LLM fast-path: exact term only (after strip)."""
    normalized = _normalize_text(query_or_label)
    if not normalized:
        return None

    entry = _match_exact(normalized)
    if entry is not None:
        return entry

    cleaned = _strip_non_class_tokens(normalized)
    if not cleaned:
        return None
    return _match_exact(cleaned)


def build_catalog_prompt_section() -> str:
    lines: list[str] = []
    for entry in YOLO_CLASS_CATALOG:
        lines.append(
            f"- {entry.canonical_label}: "
            f"clase_yolo={entry.clase_yolo}; "
            f"ES={entry.synonyms_es}; "
            f"EN={entry.synonyms_en}"
        )
    return "\n".join(lines)


def resolve_clase_yolo_from_canonical(canonical_label: str | None) -> list[str]:
    entry = find_catalog_entry(canonical_label or "")
    if entry is None:
        return []
    return list(entry.clase_yolo)


def resolve_clase_yolo_from_query(query: str) -> list[str]:
    entry = find_catalog_entry(query)
    if entry is None:
        return []
    return list(entry.clase_yolo)


def all_catalog_clase_yolo() -> set[str]:
    return {cls for entry in YOLO_CLASS_CATALOG for cls in entry.clase_yolo}


def _resolve_entry_from_terms(terms: list[str]) -> YoloClassEntry | None:
    for term in terms:
        if not term:
            continue
        entry = find_catalog_entry(term)
        if entry is not None:
            return entry
    return None


def resolve_spatial_query(structured: StructuredQuery, query: str) -> StructuredQuery:
    parsed = parse_spatial_relation(query)
    current = structured
    if parsed is not None:
        current = merge_spatial_parse_into_structured(current, parsed)

    if current.intent != "search_spatial" and current.relation is None:
        return current

    target_terms = [
        current.target_canonical_label or "",
        current.target_label or "",
        current.canonical_label or "",
        current.object_label or "",
        parsed.target_fragment if parsed else "",
    ]
    reference_terms = [
        current.reference_canonical_label or "",
        current.reference_label or "",
        parsed.reference_fragment if parsed else "",
    ]

    target_entry = _resolve_entry_from_terms(target_terms)
    reference_entry = _resolve_entry_from_terms(reference_terms)

    if target_entry is None or reference_entry is None:
        # Incomplete spatial parse — leave unresolved so use case can error clearly.
        updates: dict[str, object] = {"intent": "search_spatial"}
        if current.relation is None and parsed is not None:
            updates["relation"] = parsed.relation
        if target_entry is not None:
            updates.update(
                {
                    "target_canonical_label": target_entry.canonical_label,
                    "target_clase_yolo": list(target_entry.clase_yolo),
                    "canonical_label": target_entry.canonical_label,
                    "clase_yolo_candidates": list(target_entry.clase_yolo),
                    "target_label": current.target_label
                    or current.object_label
                    or (parsed.target_fragment if parsed else None),
                    "object_label": current.object_label
                    or current.target_label
                    or (parsed.target_fragment if parsed else None),
                }
            )
        if reference_entry is not None:
            updates.update(
                {
                    "reference_canonical_label": reference_entry.canonical_label,
                    "reference_clase_yolo": list(reference_entry.clase_yolo),
                    "reference_label": current.reference_label
                    or (parsed.reference_fragment if parsed else None),
                }
            )
        return current.model_copy(update=updates)

    attributes = normalize_attributes(current.attributes)
    if not attributes:
        attributes = extract_attributes_from_query(
            parsed.target_fragment if parsed else (current.target_label or query)
        )

    target_label = (
        current.target_label
        or current.object_label
        or (parsed.target_fragment if parsed else None)
    )
    reference_label = current.reference_label or (
        parsed.reference_fragment if parsed else None
    )

    return current.model_copy(
        update={
            "intent": "search_spatial",
            "relation": current.relation or (parsed.relation if parsed else "near"),
            "target_label": target_label,
            "target_canonical_label": target_entry.canonical_label,
            "target_clase_yolo": list(target_entry.clase_yolo),
            "reference_label": reference_label,
            "reference_canonical_label": reference_entry.canonical_label,
            "reference_clase_yolo": list(reference_entry.clase_yolo),
            "canonical_label": target_entry.canonical_label,
            "object_label": target_label,
            "clase_yolo_candidates": list(target_entry.clase_yolo),
            "attributes": attributes,
        }
    )


def _apply_simple_class_fallback(
    structured: StructuredQuery, query: str
) -> StructuredQuery:
    # Prefer LLM labels over matching the full compound query string.
    lookup_terms = [
        structured.target_canonical_label or "",
        structured.canonical_label or "",
        structured.target_label or "",
        structured.object_label or "",
        query,
    ]
    entry = _resolve_entry_from_terms(lookup_terms)

    if entry is not None:
        candidates = list(entry.clase_yolo)
    else:
        candidates = list(structured.clase_yolo_candidates)
        valid_classes = all_catalog_clase_yolo()
        if not candidates or not set(candidates).issubset(valid_classes):
            candidates = resolve_clase_yolo_from_canonical(structured.canonical_label)
        if not candidates:
            candidates = resolve_clase_yolo_from_query(query)
        if candidates and entry is None:
            entry = find_catalog_entry(structured.canonical_label or "") or find_catalog_entry(
                query
            )

    if not candidates:
        return structured

    updates: dict[str, object] = {
        "clase_yolo_candidates": candidates,
        "target_clase_yolo": candidates,
    }
    if structured.intent not in ("search_class", "search_spatial"):
        updates["intent"] = "search_class"

    attributes = normalize_attributes(structured.attributes)
    if not attributes:
        attributes = extract_attributes_from_query(query)
    if attributes:
        updates["attributes"] = attributes

    if entry is not None:
        updates["canonical_label"] = entry.canonical_label
        updates["target_canonical_label"] = entry.canonical_label
        if not structured.object_label:
            updates["object_label"] = query.strip()
        if not structured.target_label:
            updates["target_label"] = structured.object_label or query.strip()

    return structured.model_copy(update=updates)


def apply_catalog_fallback(structured: StructuredQuery, query: str) -> StructuredQuery:
    parsed = parse_spatial_relation(query)
    is_spatial = (
        structured.intent == "search_spatial"
        or structured.relation is not None
        or parsed is not None
    )

    if is_spatial:
        return resolve_spatial_query(structured, query)

    return _apply_simple_class_fallback(structured, query)
