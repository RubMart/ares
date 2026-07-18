import re

LAYER_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def validate_layer_name(layer_name: str) -> str:
    if not LAYER_NAME_RE.fullmatch(layer_name):
        raise ValueError(f"Nombre de capa no válido: {layer_name!r}")
    return layer_name


def format_pgvector_literal(values: list[float]) -> str:
    parts = ",".join(f"{value:.8f}" for value in values)
    return f"[{parts}]"
