"""Shared utilities for image discovery and companion JSON paths."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}

# Web Mercator (EPSG:3857) constants for gdal2tiles XYZ tiles.
_ORIGIN_SHIFT = 20037508.342789244
_STANDARD_TILE_PX = 256
_GDAL2TILES_PATH_RE = re.compile(
    r"(?:^|[\\/])(?P<z>\d+)[\\/](?P<x>\d+)[\\/](?P<y>\d+)\.(?:png|jpg|jpeg|webp|tif|tiff)$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Gdal2TilesGeoref:
    """Georeferencing context for a north-up gdal2tiles Web Mercator tile."""

    zoom: int
    tile_x: int
    tile_y: int
    tile_pixel_size: int


def parse_gdal2tiles_path(image_path: Path) -> tuple[int, int, int] | None:
    """Return (zoom, tile_x, tile_y) when the path matches gdal2tiles z/x/y layout."""
    match = _GDAL2TILES_PATH_RE.search(image_path.as_posix())
    if not match:
        return None
    return int(match.group("z")), int(match.group("x")), int(match.group("y"))


def build_gdal2tiles_georef(
    image_path: Path,
    width: int,
    height: int,
) -> Gdal2TilesGeoref | None:
    """Build georef context for gdal2tiles XYZ tiles with uniform pixel size."""
    parsed = parse_gdal2tiles_path(image_path)
    if parsed is None:
        return None

    if width <= 0 or height <= 0 or width != height:
        return None

    zoom, tile_x, tile_y = parsed
    return Gdal2TilesGeoref(
        zoom=zoom,
        tile_x=tile_x,
        tile_y=tile_y,
        tile_pixel_size=width,
    )


def pixel_to_epsg3857(
    pixel_x: float,
    pixel_y: float,
    georef: Gdal2TilesGeoref,
) -> tuple[float, float]:
    """Convert image pixel coordinates to EPSG:3857 (Web Mercator meters)."""
    scale_to_std = _STANDARD_TILE_PX / georef.tile_pixel_size
    global_px = georef.tile_x * _STANDARD_TILE_PX + pixel_x * scale_to_std
    global_py = georef.tile_y * _STANDARD_TILE_PX + pixel_y * scale_to_std

    world_size = _STANDARD_TILE_PX * (2**georef.zoom)
    meters_per_pixel = (2 * _ORIGIN_SHIFT) / world_size
    mx = global_px * meters_per_pixel - _ORIGIN_SHIFT
    my = _ORIGIN_SHIFT - global_py * meters_per_pixel
    return round(mx, 3), round(my, 3)


def bbox_image_to_epsg3857(
    bbox: dict[str, float],
    georef: Gdal2TilesGeoref,
) -> dict[str, float]:
    x1, y1 = pixel_to_epsg3857(bbox["x1"], bbox["y1"], georef)
    x2, y2 = pixel_to_epsg3857(bbox["x2"], bbox["y2"], georef)
    return {"x1": x1, "y1": y1, "x2": x2, "y2": y2}


def obb_image_to_epsg3857(
    obb: dict,
    georef: Gdal2TilesGeoref,
) -> dict:
    points = obb.get("points", [])
    converted: list[dict[str, float]] = []
    for point in points:
        if not isinstance(point, dict) or "x" not in point or "y" not in point:
            continue
        mx, my = pixel_to_epsg3857(point["x"], point["y"], georef)
        converted.append({"x": mx, "y": my})
    return {"points": converted}


def enrich_detections_with_epsg3857(
    detections: list[dict],
    image_path: Path,
    width: int,
    height: int,
) -> list[dict]:
    """Add bbox3857 / obb3857 when the image matches gdal2tiles Mercator tiles."""
    georef = build_gdal2tiles_georef(image_path, width, height)
    if georef is None:
        return detections

    enriched: list[dict] = []
    for detection in detections:
        item = dict(detection)
        bbox = item.get("bbox")
        if isinstance(bbox, dict) and all(key in bbox for key in ("x1", "y1", "x2", "y2")):
            item["bbox3857"] = bbox_image_to_epsg3857(bbox, georef)
        obb = item.get("obb")
        if isinstance(obb, dict):
            item["obb3857"] = obb_image_to_epsg3857(obb, georef)
        enriched.append(item)
    return enriched


def is_image_file(path: Path) -> bool:
    return path.suffix.lower() in IMAGE_EXTENSIONS


def companion_json_path(image_path: Path) -> Path:
    return image_path.with_suffix(".json")


def companion_embedding_json_path(base_path: Path) -> Path:
    """Return the embeddings JSON path for an image or detection JSON stem."""
    return base_path.with_name(f"{base_path.stem}_emb.json")


def companion_thumbnail_path(image_path: Path) -> Path:
    """Return the JPEG thumbnail path for an image (e.g. 24711.png -> 24711_thumb.jpg)."""
    return image_path.with_name(f"{image_path.stem}_thumb.jpg")


def load_detection_json(json_path: Path) -> dict:
    """Load and validate a YOLO detection companion JSON file."""
    if not json_path.exists():
        raise FileNotFoundError(f"No se encontró el JSON de detecciones: {json_path.resolve()}")

    if not json_path.is_file():
        raise ValueError(f"La ruta no es un fichero JSON: {json_path.resolve()}")

    try:
        payload = json.loads(json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON inválido en {json_path.resolve()}: {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError(f"El JSON debe ser un objeto en {json_path.resolve()}")

    source_image = payload.get("source_image")
    if not isinstance(source_image, str) or not source_image.strip():
        raise ValueError(
            f"Falta o es inválido el campo 'source_image' en {json_path.resolve()}"
        )

    detections = payload.get("detections")
    if not isinstance(detections, list):
        raise ValueError(
            f"Falta o es inválido el campo 'detections' en {json_path.resolve()}"
        )

    for index, detection in enumerate(detections):
        if not isinstance(detection, dict):
            raise ValueError(
                f"La detección {index} no es un objeto en {json_path.resolve()}"
            )
        bbox = detection.get("bbox")
        if not isinstance(bbox, dict):
            raise ValueError(
                f"La detección {index} no tiene 'bbox' válido en {json_path.resolve()}"
            )
        if not all(key in bbox for key in ("x1", "y1", "x2", "y2")):
            raise ValueError(
                f"La detección {index} tiene un 'bbox' incompleto en {json_path.resolve()}"
            )

    return payload


def resolve_source_image_path(json_path: Path, payload: dict) -> Path:
    """Resolve the source image path from detection JSON metadata."""
    raw_path = Path(payload["source_image"])
    if raw_path.is_absolute():
        return raw_path
    return (json_path.parent / raw_path).resolve()


def crop_detection_axis(
    image_bgr: np.ndarray,
    detection: dict,
    padding: int = 0,
) -> np.ndarray | None:
    """Crop an axis-aligned bbox from a BGR image; return None if the crop is empty."""
    bbox = detection["bbox"]
    height, width = image_bgr.shape[:2]

    x1 = max(0, int(bbox["x1"]) - padding)
    y1 = max(0, int(bbox["y1"]) - padding)
    x2 = min(width, int(bbox["x2"]) + padding)
    y2 = min(height, int(bbox["y2"]) + padding)

    if x2 <= x1 or y2 <= y1:
        return None

    crop = image_bgr[y1:y2, x1:x2]
    if crop.size == 0:
        return None
    return crop


def discover_images(folder: Path) -> list[Path]:
    """Recursively find image files under folder, sorted by relative path."""
    if not folder.exists():
        raise FileNotFoundError(f"No se encontró la carpeta: {folder.resolve()}")

    if not folder.is_dir():
        raise ValueError(f"La ruta no es una carpeta: {folder.resolve()}")

    images = [
        path
        for path in folder.rglob("*")
        if path.is_file() and is_image_file(path)
    ]
    return sorted(images, key=lambda path: str(path.relative_to(folder)).lower())


def build_tile_id(image_path: Path | str) -> str:
    """Return gdal2tiles tile id as z/x/y from an image path."""
    parsed = parse_gdal2tiles_path(Path(image_path))
    if parsed is None:
        raise ValueError(
            f"No se pudo extraer z/x/y del tile desde la ruta: {Path(image_path).as_posix()}"
        )
    zoom, tile_x, tile_y = parsed
    return f"{zoom}/{tile_x}/{tile_y}"


def parse_tile_id(tile_id: str) -> tuple[int, int, int]:
    """Parse a tile id string z/x/y into integer components."""
    parts = tile_id.split("/")
    if len(parts) != 3:
        raise ValueError(f"tile_id inválido (se esperaba z/x/y): {tile_id!r}")
    try:
        return int(parts[0]), int(parts[1]), int(parts[2])
    except ValueError as exc:
        raise ValueError(f"tile_id inválido (z/x/y deben ser enteros): {tile_id!r}") from exc


def tile_envelope_epsg3857(
    zoom: int,
    tile_x: int,
    tile_y: int,
    tile_pixel_size: int,
) -> dict[str, float]:
    """Return the axis-aligned EPSG:3857 envelope of a gdal2tiles tile."""
    georef = Gdal2TilesGeoref(
        zoom=zoom,
        tile_x=tile_x,
        tile_y=tile_y,
        tile_pixel_size=tile_pixel_size,
    )
    x1, y1 = pixel_to_epsg3857(0, 0, georef)
    x2, y2 = pixel_to_epsg3857(tile_pixel_size, tile_pixel_size, georef)
    return {
        "x1": min(x1, x2),
        "y1": min(y1, y2),
        "x2": max(x1, x2),
        "y2": max(y1, y2),
    }


def union_envelopes_3857(envelopes: list[dict[str, float]]) -> dict[str, float]:
    """Merge multiple EPSG:3857 envelopes into one bounding box."""
    if not envelopes:
        raise ValueError("No hay envolventes para unir")
    return {
        "x1": min(envelope["x1"] for envelope in envelopes),
        "y1": min(envelope["y1"] for envelope in envelopes),
        "x2": max(envelope["x2"] for envelope in envelopes),
        "y2": max(envelope["y2"] for envelope in envelopes),
    }


def envelope_3857_to_sql(envelope: dict[str, float], srid: int = 3857) -> str:
    """Convert an EPSG:3857 envelope dict to a PostGIS SQL expression."""
    return (
        f"ST_SetSRID(ST_MakeEnvelope("
        f"{envelope['x1']}, {envelope['y1']}, {envelope['x2']}, {envelope['y2']}), {srid})"
    )


def layer_bbox_sql_from_tile_ids(tile_ids: set[str], tile_pixel_size: int) -> str:
    """Build a PostGIS envelope SQL for the union of all gdal2tiles tiles."""
    envelopes = [
        tile_envelope_epsg3857(*parse_tile_id(tile_id), tile_pixel_size)
        for tile_id in sorted(tile_ids)
    ]
    return envelope_3857_to_sql(union_envelopes_3857(envelopes))


def tile_range_envelope_epsg3857(
    zoom: int,
    tile_x_min: int,
    tile_x_max: int,
    tile_y_min: int,
    tile_y_max: int,
    tile_pixel_size: int = _STANDARD_TILE_PX,
) -> dict[str, float]:
    """Return the EPSG:3857 envelope covering a gdal2tiles z/x/y tile range."""
    top_left = Gdal2TilesGeoref(
        zoom=zoom,
        tile_x=tile_x_min,
        tile_y=tile_y_min,
        tile_pixel_size=tile_pixel_size,
    )
    bottom_right = Gdal2TilesGeoref(
        zoom=zoom,
        tile_x=tile_x_max,
        tile_y=tile_y_max,
        tile_pixel_size=tile_pixel_size,
    )
    x1, y1 = pixel_to_epsg3857(0, 0, top_left)
    x2, y2 = pixel_to_epsg3857(tile_pixel_size, tile_pixel_size, bottom_right)
    return {
        "x1": min(x1, x2),
        "y1": min(y1, y2),
        "x2": max(x1, x2),
        "y2": max(y1, y2),
    }


def parse_mapml_tile_extent(mapml_path: Path) -> tuple[int, int, int, int, int]:
    """Parse z/x/y min/max tile indices from a gdal2tiles mapml.mapml file."""
    text = mapml_path.read_text(encoding="utf-8")
    patterns = {
        "z": r'name="z"[^>]*value="(?P<value>\d+)"',
        "x_min": r'axis="column"[^>]*min="(?P<value>\d+)"',
        "x_max": r'axis="column"[^>]*max="(?P<value>\d+)"',
        "y_min": r'axis="row"[^>]*min="(?P<value>\d+)"',
        "y_max": r'axis="row"[^>]*max="(?P<value>\d+)"',
    }
    values: dict[str, int] = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, text)
        if not match:
            raise ValueError(
                f"No se pudo leer '{key}' en {mapml_path.resolve()}"
            )
        values[key] = int(match.group("value"))

    return values["z"], values["x_min"], values["x_max"], values["y_min"], values["y_max"]


def discover_mapml_extents_near_cog(cog_path: Path) -> list[tuple[int, int, int, int, int]]:
    """Find gdal2tiles mapml extents in tiles*/ folders next to a COG file."""
    if not cog_path.exists():
        raise FileNotFoundError(f"No se encontró el COG: {cog_path.resolve()}")

    extents: list[tuple[int, int, int, int, int]] = []
    for mapml_path in sorted(cog_path.parent.glob("tiles*/mapml.mapml")):
        extents.append(parse_mapml_tile_extent(mapml_path))
    return extents


def _parse_geotiff_epsg(geokeys: tuple | list) -> int | None:
    """Extract EPSG code from a GeoKeyDirectoryTag (ProjectedCS or Geographic)."""
    if len(geokeys) < 4:
        return None

    key_count = int(geokeys[3])
    # Each key: id, TIFFTagLocation, count, value/offset
    for offset in range(4, 4 + key_count * 4, 4):
        if offset + 3 >= len(geokeys):
            break
        key_id = int(geokeys[offset])
        location = int(geokeys[offset + 1])
        value = int(geokeys[offset + 3])
        # 3072 = ProjectedCSTypeGeoKey, 2048 = GeographicTypeGeoKey
        if key_id in {3072, 2048} and location == 0 and value > 0:
            return value
    return None


def read_geotiff_native_envelope(cog_path: Path) -> tuple[int, dict[str, float]]:
    """
    Read the native CRS EPSG and axis-aligned envelope from GeoTIFF tags.

    Supports north-up images with ModelTiepointTag + ModelPixelScaleTag
    (typical COG from gdal_translate). Does not load raster pixels.
    """
    from PIL import Image

    previous_limit = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = None
    try:
        with Image.open(cog_path) as image:
            tags = image.tag_v2
            width = int(tags[256])
            height = int(tags[257])
            scale = tags.get(33550)  # ModelPixelScaleTag
            tie = tags.get(33922)  # ModelTiepointTag
            geokeys = tags.get(34735)  # GeoKeyDirectoryTag
    finally:
        Image.MAX_IMAGE_PIXELS = previous_limit

    if not scale or len(scale) < 2:
        raise ValueError(
            f"El GeoTIFF no tiene ModelPixelScaleTag usable: {cog_path.resolve()}"
        )
    if not tie or len(tie) < 5:
        raise ValueError(
            f"El GeoTIFF no tiene ModelTiepointTag usable: {cog_path.resolve()}"
        )
    if not geokeys:
        raise ValueError(
            f"El GeoTIFF no tiene GeoKeyDirectoryTag (CRS): {cog_path.resolve()}"
        )

    epsg = _parse_geotiff_epsg(geokeys)
    if epsg is None:
        raise ValueError(
            f"No se pudo leer el EPSG del GeoTIFF: {cog_path.resolve()}"
        )

    pixel_i, pixel_j = float(tie[0]), float(tie[1])
    if abs(pixel_i) > 1e-6 or abs(pixel_j) > 1e-6:
        raise ValueError(
            f"Solo se soporta ModelTiepoint en píxel (0,0); "
            f"recibido ({pixel_i}, {pixel_j}) en {cog_path.resolve()}"
        )

    sx = float(scale[0])
    sy = float(scale[1])
    origin_x = float(tie[3])
    origin_y = float(tie[4])
    # GeoTIFF: Y scale is stored positive; north-up images decrease northing with row.
    return epsg, {
        "x1": origin_x,
        "y1": origin_y - height * sy,
        "x2": origin_x + width * sx,
        "y2": origin_y,
    }


def transform_envelope_to_epsg3857(
    source_epsg: int,
    envelope: dict[str, float],
) -> dict[str, float]:
    """Reproject an axis-aligned envelope to EPSG:3857 (corner hull)."""
    if source_epsg == 3857:
        return {
            "x1": round(min(envelope["x1"], envelope["x2"]), 3),
            "y1": round(min(envelope["y1"], envelope["y2"]), 3),
            "x2": round(max(envelope["x1"], envelope["x2"]), 3),
            "y2": round(max(envelope["y1"], envelope["y2"]), 3),
        }

    try:
        from pyproj import Transformer
    except ImportError as exc:
        raise ImportError(
            "Se necesita pyproj para reproyectar el bbox del COG a EPSG:3857. "
            "Instala con: pip install pyproj"
        ) from exc

    transformer = Transformer.from_crs(source_epsg, 3857, always_xy=True)
    corners = [
        (envelope["x1"], envelope["y1"]),
        (envelope["x2"], envelope["y1"]),
        (envelope["x2"], envelope["y2"]),
        (envelope["x1"], envelope["y2"]),
    ]
    projected = [transformer.transform(x, y) for x, y in corners]
    xs = [point[0] for point in projected]
    ys = [point[1] for point in projected]
    return {
        "x1": round(min(xs), 3),
        "y1": round(min(ys), 3),
        "x2": round(max(xs), 3),
        "y2": round(max(ys), 3),
    }


def cog_envelope_epsg3857_from_geotiff(cog_path: Path) -> dict[str, float]:
    """Compute the true COG envelope in EPSG:3857 from GeoTIFF georeferencing."""
    source_epsg, native = read_geotiff_native_envelope(cog_path)
    return transform_envelope_to_epsg3857(source_epsg, native)


def cog_envelope_epsg3857_from_mapml(cog_path: Path) -> dict[str, float]:
    """Fallback: envelope of adjacent gdal2tiles mapml tile ranges (tile-snapped)."""
    extents = discover_mapml_extents_near_cog(cog_path)
    if not extents:
        raise ValueError(
            f"No se encontraron ficheros tiles*/mapml.mapml junto a {cog_path}. "
            "Genera primero el piramidado gdal2tiles o indica otra ruta."
        )

    zoom, tile_x_min, tile_x_max, tile_y_min, tile_y_max = min(
        extents, key=lambda item: item[0]
    )
    return tile_range_envelope_epsg3857(
        zoom,
        tile_x_min,
        tile_x_max,
        tile_y_min,
        tile_y_max,
    )


def cog_bbox_sql_from_path(cog_path: Path) -> str:
    """
    Resolve a COG bounding box SQL expression in EPSG:3857.

    Prefers the GeoTIFF georeferencing (true raster extent). Falls back to the
    adjacent gdal2tiles mapml tile range only if geotags/reprojection fail —
    that fallback is tile-aligned and can be displaced vs the COG.
    """
    cog_path = cog_path.resolve()
    if not cog_path.exists():
        raise FileNotFoundError(f"No se encontró el COG: {cog_path}")

    try:
        envelope = cog_envelope_epsg3857_from_geotiff(cog_path)
    except (OSError, ValueError, ImportError, KeyError) as geotiff_exc:
        try:
            envelope = cog_envelope_epsg3857_from_mapml(cog_path)
        except (FileNotFoundError, ValueError) as mapml_exc:
            raise ValueError(
                f"No se pudo calcular el bbox del COG desde geotags ({geotiff_exc}) "
                f"ni desde mapml ({mapml_exc})."
            ) from mapml_exc
        print(
            "Aviso: bbox del catálogo calculado desde tiles mapml (alineado a malla XYZ); "
            f"no desde geotags del COG ({geotiff_exc}). "
            "Puede quedar desplazado respecto al ráster real.",
            flush=True,
        )

    return envelope_3857_to_sql(envelope)


def resolve_cog_reference(cog_path: Path | None, cog_url: str | None) -> str:
    """Return the COG reference stored in the catalog."""
    if cog_path is not None:
        return str(cog_path.resolve())
    if cog_url is not None and cog_url.strip():
        return cog_url.strip()
    raise ValueError("Indica --cog-path o --cog-url para registrar el COG en el catálogo.")


def tile_pixel_size_from_detection_json(detection_payload: dict) -> int:
    """Read square tile pixel size from a detection JSON image_size block."""
    image_size = detection_payload.get("image_size")
    if not isinstance(image_size, dict):
        raise ValueError("Falta o es inválido el campo 'image_size' en el JSON de detecciones")

    width = image_size.get("width")
    height = image_size.get("height")
    if not isinstance(width, int) or not isinstance(height, int):
        raise ValueError("image_size.width/height deben ser enteros")
    if width <= 0 or height <= 0 or width != height:
        raise ValueError("image_size debe ser cuadrado y mayor que 0")

    return width


def discover_embedding_jsons(folder: Path) -> list[Path]:
    """Recursively find *_emb.json files under folder, sorted by relative path."""
    if not folder.exists():
        raise FileNotFoundError(f"No se encontró la carpeta: {folder.resolve()}")

    if not folder.is_dir():
        raise ValueError(f"La ruta no es una carpeta: {folder.resolve()}")

    embedding_paths = [
        path
        for path in folder.rglob("*_emb.json")
        if path.is_file()
    ]
    return sorted(embedding_paths, key=lambda path: str(path.relative_to(folder)).lower())


def load_embedding_json(json_path: Path) -> dict:
    """Load and validate a CLIP embeddings companion JSON file."""
    if not json_path.exists():
        raise FileNotFoundError(f"No se encontró el JSON de embeddings: {json_path.resolve()}")

    if not json_path.is_file():
        raise ValueError(f"La ruta no es un fichero JSON: {json_path.resolve()}")

    try:
        payload = json.loads(json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON inválido en {json_path.resolve()}: {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError(f"El JSON debe ser un objeto en {json_path.resolve()}")

    source_image = payload.get("source_image")
    source_detection_json = payload.get("source_detection_json")
    if not isinstance(source_image, str) or not source_image.strip():
        raise ValueError(
            f"Falta o es inválido el campo 'source_image' en {json_path.resolve()}"
        )
    if not isinstance(source_detection_json, str) or not source_detection_json.strip():
        raise ValueError(
            f"Falta o es inválido el campo 'source_detection_json' en {json_path.resolve()}"
        )

    embedding_dim = payload.get("embedding_dim")
    if not isinstance(embedding_dim, int) or embedding_dim <= 0:
        raise ValueError(
            f"Falta o es inválido el campo 'embedding_dim' en {json_path.resolve()}"
        )

    embeddings = payload.get("embeddings")
    if not isinstance(embeddings, list):
        raise ValueError(
            f"Falta o es inválido el campo 'embeddings' en {json_path.resolve()}"
        )

    for index, entry in enumerate(embeddings):
        if not isinstance(entry, dict):
            raise ValueError(
                f"El embedding {index} no es un objeto en {json_path.resolve()}"
            )
        detection_index = entry.get("detection_index")
        if not isinstance(detection_index, int) or detection_index < 0:
            raise ValueError(
                f"El embedding {index} no tiene 'detection_index' válido en {json_path.resolve()}"
            )
        class_name = entry.get("class_name")
        if not isinstance(class_name, str) or not class_name.strip():
            raise ValueError(
                f"El embedding {index} no tiene 'class_name' válido en {json_path.resolve()}"
            )
        source_model = entry.get("source_model")
        if not isinstance(source_model, str) or not source_model.strip():
            raise ValueError(
                f"El embedding {index} no tiene 'source_model' válido en {json_path.resolve()}"
            )
        confidence = entry.get("confidence")
        if not isinstance(confidence, (int, float)):
            raise ValueError(
                f"El embedding {index} no tiene 'confidence' válido en {json_path.resolve()}"
            )
        vector = entry.get("embedding")
        if not isinstance(vector, list) or len(vector) != embedding_dim:
            raise ValueError(
                f"El embedding {index} no tiene un vector de dimensión "
                f"{embedding_dim} en {json_path.resolve()}"
            )

    return payload


def sql_escape(text: str) -> str:
    """Escape single quotes for SQL string literals."""
    return text.replace("'", "''")


def format_pgvector_literal(values: list[float], dim: int) -> str:
    """Format a pgvector literal for SQL INSERT statements."""
    if len(values) != dim:
        raise ValueError(
            f"Se esperaban {dim} valores para el vector, recibidos: {len(values)}"
        )
    formatted = ",".join(repr(float(value)) for value in values)
    return f"'[{formatted}]'::vector({dim})"


def detection_geometry_3857(detection: dict) -> str | None:
    """Return a PostGIS SQL expression for the detection geometry in EPSG:3857."""
    bbox_type = detection.get("bbox_type", "axis")
    if bbox_type == "obb":
        obb3857 = detection.get("obb3857")
        if not isinstance(obb3857, dict):
            return None

        points = obb3857.get("points", [])
        if not isinstance(points, list) or len(points) < 3:
            return None

        coords: list[str] = []
        for point in points:
            if not isinstance(point, dict) or "x" not in point or "y" not in point:
                return None
            coords.append(f"{point['x']} {point['y']}")

        if coords[0] != coords[-1]:
            coords.append(coords[0])

        wkt = f"POLYGON(({', '.join(coords)}))"
        return f"ST_SetSRID(ST_GeomFromText('{wkt}'), 3857)"

    bbox3857 = detection.get("bbox3857")
    if not isinstance(bbox3857, dict):
        return None

    required = ("x1", "y1", "x2", "y2")
    if not all(key in bbox3857 for key in required):
        return None

    x1 = float(bbox3857["x1"])
    y1 = float(bbox3857["y1"])
    x2 = float(bbox3857["x2"])
    y2 = float(bbox3857["y2"])
    xmin, xmax = min(x1, x2), max(x1, x2)
    ymin, ymax = min(y1, y2), max(y1, y2)
    return f"ST_SetSRID(ST_MakeEnvelope({xmin}, {ymin}, {xmax}, {ymax}), 3857)"
