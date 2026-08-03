#!/usr/bin/env python3
"""Generate PostGIS + pgvector SQL from YOLO detections and CLIP embeddings."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from tqdm import tqdm

from utils import (
    build_tile_id,
    cog_bbox_sql_from_path,
    detection_geometry_3857,
    discover_embedding_jsons,
    format_pgvector_literal,
    layer_bbox_sql_from_tile_ids,
    load_detection_json,
    load_embedding_json,
    resolve_cog_reference,
    sql_escape,
    tile_pixel_size_from_detection_json,
)

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
DEFAULT_INSERT_BATCH_SIZE = 50
DEFAULT_OUTPUT_DIR = REPO_ROOT
DEFAULT_CATALOG_TABLE = "detecciones_catalogo"
SUMMARY_FILENAME = "embed2psql_summary.json"
VECTOR_DIM = 512
EPSG_3857 = 3857
LAYER_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

EPILOG = f"""
Parámetros obligatorios:
  --layer NOMBRE   Nombre de la tabla/capa en PostgreSQL
  --cog-path RUTA  Ruta local al COG (recomendado; bbox EPSG:3857 desde geotags)
  --cog-url URL    URL HTTP(S) del COG (visor); si se pasa con --cog-path, se guarda la URL

Parámetros (modo entrada única):
  input            Ruta a un JSON de embeddings (*_emb.json)

Parámetros (modo batch):
  --batch CARPETA  Procesa recursivamente todos los *_emb.json de la carpeta

Parámetros opcionales:
  --output-dir DIR        Carpeta de salida SQL (por defecto: raíz del proyecto)
  --insert-batch-size N   Filas por sentencia INSERT (por defecto: {DEFAULT_INSERT_BATCH_SIZE})
  --min-conf CONF         Filtra embeddings por confianza mínima (por defecto: 0)
  --classes LISTA         Filtra por class_name separados por comas
  --source-model M        Filtra por source_model del JSON
  --strict                Falla si falta geometría EPSG:3857 en alguna detección
  --catalog-table NOMBRE  Tabla catálogo de capas (por defecto: {DEFAULT_CATALOG_TABLE})

Salida:
  Genera {DEFAULT_CATALOG_TABLE}_schema.sql, {{capa}}_schema.sql,
  {DEFAULT_CATALOG_TABLE}_data.sql y {{capa}}_data.sql.
  El catálogo usa el bbox real del COG (--cog-path, geotags→3857) o, si falla,
  el rango mapml de tiles (alineado a malla XYZ; puede desplazarse). Con solo
  --cog-url, usa la unión de tiles. Si hay --cog-url, esa URL se guarda en
  cog_url (necesaria para el visor); --cog-path sigue calculando el bbox.
  Detalle: doc/cog-y-visor.md
  En modo batch, genera {SUMMARY_FILENAME} en la raíz de la carpeta indicada.

Ejemplos:
  python embed2psql.py --layer madrid_detections_example \\
      --cog-path D:/TFM/cog_madrid/madrid_recortada_cog.tif \\
      --cog-url http://127.0.0.1:4040/madrid_recortada_cog.tif \\
      --batch pruebas/tiles16/

  python embed2psql.py --layer madrid_detections_example \\
      --cog-path D:/TFM/cog_madrid/madrid_recortada_cog.tif \\
      pruebas/tiles16/16/32101/24711_emb.json

  python embed2psql.py --layer madrid_detections_example \\
      --cog-url https://example.com/madrid.cog \\
      --batch pruebas/tiles16/ --output-dir sql/
"""


@dataclass(frozen=True)
class SqlRow:
    tile_id: str
    clase_yolo: str
    modelo_deteccion: str
    embedding_sql: str
    geom_sql: str
    confianza: float


def report_error(message: str, *, hint: str | None = None) -> None:
    print(f"Error: {message}", file=sys.stderr)
    if hint:
        print(f"Sugerencia: {hint}", file=sys.stderr)


def confidence_value(raw_value: str) -> float:
    try:
        confidence = float(raw_value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"'{raw_value}' no es un número válido. "
            "Usa un decimal entre 0 y 1, por ejemplo: 0.25"
        ) from exc

    if not 0.0 <= confidence <= 1.0:
        raise argparse.ArgumentTypeError(
            f"El umbral de confianza debe estar entre 0 y 1 (recibido: {confidence})."
        )
    return confidence


def positive_int(raw_value: str) -> int:
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"'{raw_value}' no es un entero válido."
        ) from exc

    if value <= 0:
        raise argparse.ArgumentTypeError(
            f"El valor debe ser mayor que 0 (recibido: {value})."
        )
    return value


def parse_classes(raw_value: str | None) -> list[str] | None:
    if raw_value is None:
        return None

    classes = [item.strip() for item in raw_value.split(",") if item.strip()]
    if not classes:
        raise argparse.ArgumentTypeError(
            "Indica al menos una clase en --classes, por ejemplo: car,Building"
        )
    return classes


def validate_layer_name(layer: str) -> str:
    if not LAYER_NAME_RE.fullmatch(layer):
        raise argparse.ArgumentTypeError(
            f"'{layer}' no es un nombre de capa válido. "
            "Usa letras, números y guiones bajos, empezando por letra o _."
        )
    return layer


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Genera SQL para cargar detecciones YOLO con embeddings CLIP "
            "en PostgreSQL con PostGIS y pgvector."
        ),
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--layer",
        type=validate_layer_name,
        required=True,
        metavar="NOMBRE",
        help="Nombre de la tabla/capa en PostgreSQL.",
    )
    parser.add_argument(
        "--cog-path",
        type=Path,
        default=None,
        metavar="RUTA",
        help="Ruta local al COG; bbox EPSG:3857 desde geotags. Sin --cog-url, se guarda esta ruta en cog_url.",
    )
    parser.add_argument(
        "--cog-url",
        default=None,
        metavar="URL",
        help="URL HTTP(S) del COG para el catálogo/visor. Con --cog-path, prevalece en cog_url.",
    )
    parser.add_argument(
        "--catalog-table",
        type=validate_layer_name,
        default=DEFAULT_CATALOG_TABLE,
        metavar="NOMBRE",
        help=f"Nombre de la tabla catálogo (por defecto: {DEFAULT_CATALOG_TABLE}).",
    )
    parser.add_argument(
        "input",
        type=Path,
        nargs="?",
        default=None,
        metavar="input",
        help="Ruta a un JSON de embeddings (obligatorio salvo con --batch).",
    )
    parser.add_argument(
        "--batch",
        type=Path,
        metavar="CARPETA",
        help="Procesa recursivamente todos los *_emb.json de la carpeta.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        metavar="DIR",
        help=f"Carpeta de salida para los ficheros SQL (por defecto: {DEFAULT_OUTPUT_DIR}).",
    )
    parser.add_argument(
        "--insert-batch-size",
        type=positive_int,
        default=DEFAULT_INSERT_BATCH_SIZE,
        metavar="N",
        help=f"Filas por sentencia INSERT (por defecto: {DEFAULT_INSERT_BATCH_SIZE}).",
    )
    parser.add_argument(
        "--min-conf",
        type=confidence_value,
        default=0.0,
        metavar="CONF",
        help="Filtra embeddings con confianza menor que este umbral (por defecto: 0).",
    )
    parser.add_argument(
        "--classes",
        type=parse_classes,
        default=None,
        metavar="LISTA",
        help="Filtra por class_name separados por comas.",
    )
    parser.add_argument(
        "--source-model",
        default=None,
        metavar="M",
        help="Filtra por source_model del JSON de embeddings.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Falla si alguna detección no tiene geometría EPSG:3857.",
    )

    if len(sys.argv) == 1:
        parser.print_help()
        print(
            "\nFalta el parámetro obligatorio: --layer NOMBRE, --cog-path o --cog-url, "
            "e input o --batch CARPETA",
            file=sys.stderr,
        )
        raise SystemExit(2)

    args = parser.parse_args()

    if args.batch and args.input:
        parser.error("No combines --batch con el argumento input. Usa solo uno de los dos modos.")

    if not args.batch and args.input is None:
        parser.error("Indica un JSON de embeddings o usa --batch CARPETA.")

    if args.cog_path is None and not args.cog_url:
        parser.error("Indica --cog-path RUTA o --cog-url URL.")

    return args


def resolve_detection_json_path(emb_path: Path, emb_payload: dict) -> Path:
    raw_path = Path(emb_payload["source_detection_json"])
    if raw_path.is_absolute():
        return raw_path
    return (emb_path.parent / raw_path).resolve()


def filter_embeddings(
    embeddings: list[dict],
    *,
    min_confidence: float,
    classes: list[str] | None,
    source_model: str | None,
) -> list[dict]:
    class_filter = {name.lower() for name in classes} if classes else None
    filtered: list[dict] = []

    for entry in embeddings:
        confidence = entry.get("confidence")
        if not isinstance(confidence, (int, float)) or confidence < min_confidence:
            continue

        if class_filter is not None:
            class_name = entry.get("class_name")
            if not isinstance(class_name, str) or class_name.lower() not in class_filter:
                continue

        if source_model is not None:
            model_name = entry.get("source_model")
            if model_name != source_model:
                continue

        filtered.append(entry)

    return filtered


def values_match(left: object, right: object, *, tolerance: float = 1e-4) -> bool:
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return abs(float(left) - float(right)) <= tolerance
    return left == right


def verify_detection_match(emb_entry: dict, detection: dict, emb_path: Path) -> None:
    checks = (
        ("class_name", emb_entry.get("class_name"), detection.get("class_name")),
        ("confidence", emb_entry.get("confidence"), detection.get("confidence")),
        ("source_model", emb_entry.get("source_model"), detection.get("source_model")),
    )
    for field, emb_value, det_value in checks:
        if not values_match(emb_value, det_value):
            detection_index = emb_entry.get("detection_index")
            raise ValueError(
                f"Inconsistencia en {emb_path.resolve()}: "
                f"detection_index={detection_index}, campo '{field}' "
                f"embedding={emb_value!r} vs detección={det_value!r}"
            )


def build_sql_row(
    emb_entry: dict,
    detection: dict,
    tile_id: str,
    embedding_dim: int,
) -> SqlRow:
    embedding_sql = format_pgvector_literal(emb_entry["embedding"], embedding_dim)
    geom_sql = detection_geometry_3857(detection)
    if geom_sql is None:
        raise ValueError(
            f"La detección {emb_entry['detection_index']} no tiene geometría EPSG:3857 válida"
        )

    return SqlRow(
        tile_id=tile_id,
        clase_yolo=emb_entry["class_name"],
        modelo_deteccion=emb_entry["source_model"],
        embedding_sql=embedding_sql,
        geom_sql=geom_sql,
        confianza=float(emb_entry["confidence"]),
    )


def format_insert_value(row: SqlRow) -> str:
    return (
        f"('{sql_escape(row.tile_id)}', "
        f"'{sql_escape(row.clase_yolo)}', "
        f"'{sql_escape(row.modelo_deteccion)}', "
        f"{row.embedding_sql}, "
        f"{row.geom_sql}, "
        f"{row.confianza}, "
        f"'{{}}'::jsonb)"
    )


def write_catalog_schema_sql(path: Path, catalog_table: str) -> None:
    content = f"""CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS {catalog_table} (
    id                SERIAL PRIMARY KEY,
    nombre_capa       VARCHAR NOT NULL UNIQUE,
    bbox              GEOMETRY(Polygon, {EPSG_3857}) NOT NULL,
    cog_url           TEXT NOT NULL,
    total_detecciones INTEGER NOT NULL,
    total_tiles       INTEGER NOT NULL,
    metadata          JSONB NOT NULL DEFAULT '{{}}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_{catalog_table}_bbox
    ON {catalog_table} USING GIST (bbox);
"""
    path.write_text(content, encoding="utf-8")


def write_layer_schema_sql(path: Path, layer: str) -> None:
    content = f"""CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS {layer} (
    id               SERIAL PRIMARY KEY,
    tile_id          VARCHAR NOT NULL,
    clase_yolo       VARCHAR NOT NULL,
    modelo_deteccion VARCHAR NOT NULL,
    embedding        vector({VECTOR_DIM}) NOT NULL,
    geom             GEOMETRY(Polygon, {EPSG_3857}) NOT NULL,
    confianza        FLOAT NOT NULL,
    metadata         JSONB NOT NULL DEFAULT '{{}}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_{layer}_geom
    ON {layer} USING GIST (geom);

CREATE INDEX IF NOT EXISTS idx_{layer}_modelo
    ON {layer} (modelo_deteccion);

CREATE INDEX IF NOT EXISTS idx_{layer}_embedding
    ON {layer} USING hnsw (embedding vector_cosine_ops);
"""
    path.write_text(content, encoding="utf-8")


def write_layer_data_sql(
    path: Path,
    layer: str,
    rows: list[SqlRow],
    batch_size: int,
) -> None:
    lines: list[str] = []

    if not rows:
        lines.append(f"-- No hay filas para insertar en {layer}.")
    else:
        lines.extend([
            f"-- Datos para la capa {layer}",
            f"-- Total filas: {len(rows)}",
            "",
        ])
        columns = (
            "(tile_id, clase_yolo, modelo_deteccion, embedding, geom, confianza, metadata)"
        )

        for start in range(0, len(rows), batch_size):
            batch = rows[start : start + batch_size]
            values = ",\n    ".join(format_insert_value(row) for row in batch)
            lines.append(f"INSERT INTO {layer} {columns}")
            lines.append("VALUES")
            lines.append(f"    {values};")
            lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def write_catalog_data_sql(
    path: Path,
    *,
    catalog_table: str,
    catalog_layer: str,
    catalog_bbox_sql: str,
    cog_reference: str,
    total_detecciones: int,
    total_tiles: int,
) -> None:
    content = f"""-- Catálogo: registro de la capa {catalog_layer}
INSERT INTO {catalog_table}
    (nombre_capa, bbox, cog_url, total_detecciones, total_tiles, metadata)
VALUES
    (
        '{sql_escape(catalog_layer)}',
        {catalog_bbox_sql},
        '{sql_escape(cog_reference)}',
        {total_detecciones},
        {total_tiles},
        '{{}}'::jsonb
    )
ON CONFLICT (nombre_capa) DO UPDATE SET
    bbox = EXCLUDED.bbox,
    cog_url = EXCLUDED.cog_url,
    total_detecciones = EXCLUDED.total_detecciones,
    total_tiles = EXCLUDED.total_tiles;
"""
    path.write_text(content, encoding="utf-8")


@dataclass
class ProcessResult:
    rows: list[SqlRow]
    skipped_geom: int
    tile_id: str
    tile_pixel_size: int


def process_embedding_file(
    emb_path: Path,
    *,
    min_confidence: float,
    classes: list[str] | None,
    source_model: str | None,
    strict: bool,
) -> ProcessResult:
    emb_payload = load_embedding_json(emb_path)
    detection_json_path = resolve_detection_json_path(emb_path, emb_payload)
    detection_payload = load_detection_json(detection_json_path)
    detections = detection_payload["detections"]
    embedding_dim = emb_payload["embedding_dim"]

    tile_id = build_tile_id(emb_payload["source_image"])
    tile_pixel_size = tile_pixel_size_from_detection_json(detection_payload)
    filtered_entries = filter_embeddings(
        emb_payload["embeddings"],
        min_confidence=min_confidence,
        classes=classes,
        source_model=source_model,
    )

    rows: list[SqlRow] = []
    skipped_geom = 0

    for emb_entry in filtered_entries:
        detection_index = emb_entry["detection_index"]
        if detection_index >= len(detections):
            raise ValueError(
                f"detection_index={detection_index} fuera de rango en "
                f"{emb_path.resolve()} (detecciones={len(detections)})"
            )

        detection = detections[detection_index]
        verify_detection_match(emb_entry, detection, emb_path)

        try:
            rows.append(
                build_sql_row(emb_entry, detection, tile_id, embedding_dim)
            )
        except ValueError as exc:
            if strict:
                raise ValueError(
                    f"{emb_path.resolve()}: {exc}"
                ) from exc
            skipped_geom += 1

    return ProcessResult(
        rows=rows,
        skipped_geom=skipped_geom,
        tile_id=tile_id,
        tile_pixel_size=tile_pixel_size,
    )


def build_summary(
    *,
    layer: str,
    catalog_table: str,
    cog_path: Path | None,
    cog_url: str | None,
    catalog_bbox_sql: str,
    source_folder: Path | None,
    embedding_paths: list[Path],
    processed: int,
    failed: int,
    total_rows: int,
    skipped_geom: int,
    rows_by_class: Counter[str],
    rows_by_model: Counter[str],
    tile_ids: set[str],
    catalog_schema_path: Path,
    layer_schema_path: Path,
    catalog_data_path: Path,
    layer_data_path: Path,
    failures: list[tuple[Path, str]],
) -> dict:
    return {
        "layer": layer,
        "catalog_table": catalog_table,
        "cog_path": str(cog_path.resolve()) if cog_path else None,
        "cog_url": cog_url,
        "cog_reference": resolve_cog_reference(cog_path, cog_url),
        "catalog_bbox_sql": catalog_bbox_sql,
        "source_folder": str(source_folder.resolve()) if source_folder else None,
        "output": {
            "catalog_schema_sql": str(catalog_schema_path.resolve()),
            "layer_schema_sql": str(layer_schema_path.resolve()),
            "catalog_data_sql": str(catalog_data_path.resolve()),
            "layer_data_sql": str(layer_data_path.resolve()),
        },
        "run": {
            "processed": processed,
            "failed": failed,
            "total_embedding_files": len(embedding_paths),
        },
        "total_rows": total_rows,
        "skipped_missing_geom": skipped_geom,
        "unique_tiles": len(tile_ids),
        "rows_by_class": dict(sorted(rows_by_class.items())),
        "rows_by_model": dict(sorted(rows_by_model.items())),
        "failures": [
            {"path": str(path.resolve()), "error": message}
            for path, message in failures
        ],
    }


def write_summary(path: Path, summary: dict) -> None:
    path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def generate_sql_files(
    embedding_paths: list[Path],
    *,
    layer: str,
    catalog_table: str,
    cog_path: Path | None,
    cog_url: str | None,
    output_dir: Path,
    insert_batch_size: int,
    min_confidence: float,
    classes: list[str] | None,
    source_model: str | None,
    strict: bool,
    summary_folder: Path | None,
) -> int:
    output_dir.mkdir(parents=True, exist_ok=True)
    catalog_schema_path = output_dir / f"{catalog_table}_schema.sql"
    layer_schema_path = output_dir / f"{layer}_schema.sql"
    catalog_data_path = output_dir / f"{catalog_table}_data.sql"
    layer_data_path = output_dir / f"{layer}_data.sql"

    write_catalog_schema_sql(catalog_schema_path, catalog_table)
    write_layer_schema_sql(layer_schema_path, layer)

    try:
        cog_reference = resolve_cog_reference(cog_path, cog_url)
    except ValueError as exc:
        report_error(str(exc))
        return 1

    all_rows: list[SqlRow] = []
    rows_by_class: Counter[str] = Counter()
    rows_by_model: Counter[str] = Counter()
    tile_ids: set[str] = set()
    tile_pixel_size: int | None = None
    skipped_geom = 0
    processed = 0
    failures: list[tuple[Path, str]] = []

    progress = tqdm(embedding_paths, desc="embed2psql", unit="file")
    for emb_path in progress:
        try:
            result = process_embedding_file(
                emb_path,
                min_confidence=min_confidence,
                classes=classes,
                source_model=source_model,
                strict=strict,
            )
        except (FileNotFoundError, ValueError) as exc:
            failures.append((emb_path, str(exc)))
            continue

        if tile_pixel_size is None:
            tile_pixel_size = result.tile_pixel_size
        elif tile_pixel_size != result.tile_pixel_size:
            failures.append((
                emb_path,
                (
                    f"Tamaño de tile inconsistente: esperado {tile_pixel_size}px, "
                    f"recibido {result.tile_pixel_size}px"
                ),
            ))
            continue

        processed += 1
        skipped_geom += result.skipped_geom
        tile_ids.add(result.tile_id)
        all_rows.extend(result.rows)
        for row in result.rows:
            rows_by_class[row.clase_yolo] += 1
            rows_by_model[row.modelo_deteccion] += 1

    if processed == 0:
        report_error(
            "No se procesó ningún fichero de embeddings.",
            hint="Revisa los errores anteriores o usa --strict solo si todas las geometrías existen.",
        )
        return 1

    if tile_pixel_size is None or not tile_ids:
        report_error("No se pudo calcular el catálogo: sin tiles válidos.")
        return 1

    if cog_path is not None:
        try:
            catalog_bbox_sql = cog_bbox_sql_from_path(cog_path)
        except (FileNotFoundError, ValueError) as exc:
            report_error(str(exc))
            return 1
    else:
        catalog_bbox_sql = layer_bbox_sql_from_tile_ids(tile_ids, tile_pixel_size)

    write_layer_data_sql(layer_data_path, layer, all_rows, insert_batch_size)
    write_catalog_data_sql(
        catalog_data_path,
        catalog_table=catalog_table,
        catalog_layer=layer,
        catalog_bbox_sql=catalog_bbox_sql,
        cog_reference=cog_reference,
        total_detecciones=len(all_rows),
        total_tiles=len(tile_ids),
    )

    print(f"Catálogo SQL: {catalog_schema_path.resolve()}")
    print(f"Schema SQL:   {layer_schema_path.resolve()}")
    print(f"Catálogo data:{catalog_data_path.resolve()}")
    print(f"Data SQL:     {layer_data_path.resolve()}")
    print(f"  Capa:      {layer}")
    print(f"  Catálogo:  {catalog_table}")
    print(f"  COG:       {cog_reference}")
    print(f"  Archivos:  {processed}/{len(embedding_paths)} procesados")
    print(f"  Filas:     {len(all_rows)}")
    print(f"  Tiles:     {len(tile_ids)}")
    if skipped_geom:
        print(f"  Omitidas:  {skipped_geom} detecciones sin geometría EPSG:3857")
    if failures:
        print(f"  Fallos:    {len(failures)}")

    if summary_folder is not None:
        summary_path = summary_folder / SUMMARY_FILENAME
        summary = build_summary(
            layer=layer,
            catalog_table=catalog_table,
            cog_path=cog_path,
            cog_url=cog_url,
            catalog_bbox_sql=catalog_bbox_sql,
            source_folder=summary_folder,
            embedding_paths=embedding_paths,
            processed=processed,
            failed=len(failures),
            total_rows=len(all_rows),
            skipped_geom=skipped_geom,
            rows_by_class=rows_by_class,
            rows_by_model=rows_by_model,
            tile_ids=tile_ids,
            catalog_schema_path=catalog_schema_path,
            layer_schema_path=layer_schema_path,
            catalog_data_path=catalog_data_path,
            layer_data_path=layer_data_path,
            failures=failures,
        )
        write_summary(summary_path, summary)
        print(f"Resumen:    {summary_path.resolve()}")

    return 0 if not failures else 1


def run_single(args: argparse.Namespace) -> int:
    emb_path = args.input
    if emb_path.suffix.lower() != ".json" or not emb_path.name.endswith("_emb.json"):
        report_error(
            f"La entrada debe ser un JSON de embeddings (*_emb.json): {emb_path.resolve()}",
            hint="Genera primero los embeddings con embed.py.",
        )
        return 1

    return generate_sql_files(
        [emb_path],
        layer=args.layer,
        catalog_table=args.catalog_table,
        cog_path=args.cog_path,
        cog_url=args.cog_url,
        output_dir=args.output_dir,
        insert_batch_size=args.insert_batch_size,
        min_confidence=args.min_conf,
        classes=args.classes,
        source_model=args.source_model,
        strict=args.strict,
        summary_folder=None,
    )


def run_batch(args: argparse.Namespace) -> int:
    folder = args.batch
    try:
        embedding_paths = discover_embedding_jsons(folder)
    except (FileNotFoundError, ValueError) as exc:
        report_error(str(exc))
        return 1

    if not embedding_paths:
        report_error(
            f"No se encontraron ficheros *_emb.json en {folder.resolve()}",
            hint="Ejecuta primero embed.py en la carpeta.",
        )
        return 1

    print(f"Escaneando carpeta: {folder}")
    print(f"Encontrados {len(embedding_paths)} ficheros *_emb.json")
    print(f"Capa SQL: {args.layer}")

    return generate_sql_files(
        embedding_paths,
        layer=args.layer,
        catalog_table=args.catalog_table,
        cog_path=args.cog_path,
        cog_url=args.cog_url,
        output_dir=args.output_dir,
        insert_batch_size=args.insert_batch_size,
        min_confidence=args.min_conf,
        classes=args.classes,
        source_model=args.source_model,
        strict=args.strict,
        summary_folder=folder,
    )


def main() -> None:
    args = parse_args()
    if args.batch:
        raise SystemExit(run_batch(args))
    raise SystemExit(run_single(args))


if __name__ == "__main__":
    main()
