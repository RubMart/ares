#!/usr/bin/env python3
"""Generate 512x512 JPEG thumbnails for fast transmission of image examples."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import cv2
from tqdm import tqdm

from utils import companion_thumbnail_path, discover_images, is_image_file

DEFAULT_SIZE = 512
DEFAULT_QUALITY = 85
SUMMARY_FILENAME = "thumbnail_summary.json"

EPILOG = f"""
Parámetros (modo imagen única):
  image          Ruta a la imagen de entrada (jpg, png, bmp, webp, tif, ...)

Parámetros (modo batch):
  --batch CARPETA   Procesa recursivamente todas las imágenes de la carpeta
  --skip-existing   Salta imágenes que ya tienen un thumbnail _thumb.jpg

Parámetros opcionales:
  --size N        Tamaño cuadrado del thumbnail en píxeles (por defecto: {DEFAULT_SIZE})
  --quality N     Calidad JPEG entre 1 y 100 (por defecto: {DEFAULT_QUALITY})

Salida:
  Genera un JPEG con sufijo _thumb junto a cada imagen fuente.
  Ejemplo: 24711.png -> 24711_thumb.jpg
  En modo batch, genera {SUMMARY_FILENAME} en la raíz de la carpeta indicada.

Ejemplos:
  python thumbnail.py pruebas/tiles16/16/32101/24711.png
  python thumbnail.py --batch pruebas/tiles16/
  python thumbnail.py --batch pruebas/tiles16/ --skip-existing
  python thumbnail.py --batch pruebas/tiles16/ --quality 75
"""


def report_error(message: str, *, hint: str | None = None) -> None:
    print(f"Error: {message}", file=sys.stderr)
    if hint:
        print(f"Sugerencia: {hint}", file=sys.stderr)


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


def jpeg_quality(raw_value: str) -> int:
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"'{raw_value}' no es un entero válido."
        ) from exc

    if not 1 <= value <= 100:
        raise argparse.ArgumentTypeError(
            f"La calidad JPEG debe estar entre 1 y 100 (recibido: {value})."
        )
    return value


def is_thumbnail_source(path: Path) -> bool:
    """Return True when the path looks like an already-generated thumbnail."""
    return path.stem.endswith("_thumb")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Genera thumbnails JPEG cuadrados junto a cada imagen "
            "para transmisión rápida como ejemplos."
        ),
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "image",
        type=Path,
        nargs="?",
        default=None,
        metavar="image",
        help="Ruta a la imagen de entrada (obligatorio salvo con --batch).",
    )
    parser.add_argument(
        "--batch",
        type=Path,
        metavar="CARPETA",
        help="Procesa recursivamente todas las imágenes de la carpeta.",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="En modo batch, salta imágenes que ya tienen un fichero _thumb.jpg.",
    )
    parser.add_argument(
        "--size",
        type=positive_int,
        default=DEFAULT_SIZE,
        metavar="N",
        help=f"Tamaño cuadrado del thumbnail en píxeles (por defecto: {DEFAULT_SIZE}).",
    )
    parser.add_argument(
        "--quality",
        type=jpeg_quality,
        default=DEFAULT_QUALITY,
        metavar="N",
        help=f"Calidad JPEG entre 1 y 100 (por defecto: {DEFAULT_QUALITY}).",
    )

    if len(sys.argv) == 1:
        parser.print_help()
        print(
            "\nFalta el parámetro obligatorio: image o --batch CARPETA",
            file=sys.stderr,
        )
        raise SystemExit(2)

    args = parser.parse_args()

    if args.batch and args.image:
        parser.error("No combines --batch con el argumento image. Usa solo uno de los dos modos.")

    if not args.batch and args.image is None:
        parser.error("Indica una imagen o usa --batch CARPETA.")

    return args


@dataclass(frozen=True)
class ThumbnailResult:
    source_path: Path
    thumbnail_path: Path
    source_size_px: tuple[int, int]
    source_bytes: int
    thumbnail_bytes: int


def create_thumbnail(
    image_path: Path,
    *,
    size: int,
    quality: int,
) -> ThumbnailResult:
    if not image_path.exists():
        raise FileNotFoundError(f"No se encontró la imagen: {image_path.resolve()}")

    if not image_path.is_file():
        raise ValueError(f"La ruta no es un fichero de imagen: {image_path.resolve()}")

    if not is_image_file(image_path):
        raise ValueError(
            f"Extensión no soportada: {image_path.suffix}. "
            "Usa jpg, png, bmp, webp o tif."
        )

    if is_thumbnail_source(image_path):
        raise ValueError(
            f"El fichero parece ser un thumbnail existente: {image_path.name}"
        )

    image_bgr = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if image_bgr is None:
        raise ValueError(f"No se pudo leer la imagen: {image_path.resolve()}")

    height, width = image_bgr.shape[:2]
    if width <= 0 or height <= 0:
        raise ValueError(f"La imagen está vacía o es inválida: {image_path.resolve()}")

    thumbnail_bgr = cv2.resize(
        image_bgr,
        (size, size),
        interpolation=cv2.INTER_AREA,
    )

    thumbnail_path = companion_thumbnail_path(image_path)
    if not cv2.imwrite(
        str(thumbnail_path),
        thumbnail_bgr,
        [int(cv2.IMWRITE_JPEG_QUALITY), quality],
    ):
        raise OSError(f"No se pudo escribir el thumbnail: {thumbnail_path.resolve()}")

    source_bytes = image_path.stat().st_size
    thumbnail_bytes = thumbnail_path.stat().st_size

    return ThumbnailResult(
        source_path=image_path,
        thumbnail_path=thumbnail_path,
        source_size_px=(width, height),
        source_bytes=source_bytes,
        thumbnail_bytes=thumbnail_bytes,
    )


def print_result(result: ThumbnailResult) -> None:
    width, height = result.source_size_px
    saved = result.source_bytes - result.thumbnail_bytes
    ratio = (result.thumbnail_bytes / result.source_bytes * 100) if result.source_bytes else 0.0
    print(f"Thumbnail guardado en: {result.thumbnail_path.resolve()}")
    print(f"  Origen:      {width}x{height} ({result.source_bytes:,} bytes)")
    print(f"  Thumbnail:   {result.thumbnail_path.name} ({result.thumbnail_bytes:,} bytes, {ratio:.1f}% del original)")
    if saved > 0:
        print(f"  Ahorro:      {saved:,} bytes")


def count_subfolders(folder: Path, image_paths: list[Path]) -> int:
    subfolders = {path.parent for path in image_paths if path.parent != folder}
    return len(subfolders)


def build_file_summary_entry(
    folder: Path,
    result: ThumbnailResult,
) -> dict:
    relative_source = result.source_path.relative_to(folder)
    relative_thumbnail = result.thumbnail_path.relative_to(folder)
    width, height = result.source_size_px
    return {
        "source": relative_source.as_posix(),
        "thumbnail": relative_thumbnail.as_posix(),
        "source_size_px": [width, height],
        "source_bytes": result.source_bytes,
        "thumbnail_bytes": result.thumbnail_bytes,
    }


def build_thumbnail_summary(
    folder: Path,
    *,
    size: int,
    quality: int,
    processed: int,
    skipped: int,
    failures: list[tuple[Path, str]],
    file_entries: list[dict],
) -> dict:
    total_source_bytes = sum(entry["source_bytes"] for entry in file_entries)
    total_thumbnail_bytes = sum(entry["thumbnail_bytes"] for entry in file_entries)
    return {
        "source_folder": str(folder.resolve()),
        "thumbnail_size": size,
        "jpeg_quality": quality,
        "processed": processed,
        "skipped": skipped,
        "failed": len(failures),
        "total_source_bytes": total_source_bytes,
        "total_thumbnail_bytes": total_thumbnail_bytes,
        "total_bytes_saved": max(0, total_source_bytes - total_thumbnail_bytes),
        "files": file_entries,
        "failures": [
            {"path": str((folder / relative_path).resolve()), "error": message}
            for relative_path, message in failures
        ],
    }


def write_thumbnail_summary(
    folder: Path,
    *,
    size: int,
    quality: int,
    processed: int,
    skipped: int,
    failures: list[tuple[Path, str]],
    file_entries: list[dict],
) -> Path:
    summary_path = folder / SUMMARY_FILENAME
    summary = build_thumbnail_summary(
        folder,
        size=size,
        quality=quality,
        processed=processed,
        skipped=skipped,
        failures=failures,
        file_entries=file_entries,
    )
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return summary_path


def run_single(
    image_path: Path,
    *,
    size: int,
    quality: int,
) -> int:
    try:
        result = create_thumbnail(image_path, size=size, quality=quality)
        print_result(result)
        return 0
    except FileNotFoundError as exc:
        report_error(
            str(exc),
            hint="Comprueba que la ruta de la imagen sea correcta.",
        )
        return 1
    except ValueError as exc:
        report_error(
            str(exc),
            hint="Usa una imagen válida (jpg, png, bmp, webp, tif).",
        )
        return 1
    except OSError as exc:
        report_error(
            f"No se pudo escribir el thumbnail: {exc}",
            hint="Comprueba permisos de escritura en la carpeta de salida.",
        )
        return 1
    except Exception as exc:
        report_error(
            f"Fallo durante la generación del thumbnail: {exc}",
            hint="Revisa que la imagen sea legible y que opencv-python esté instalado.",
        )
        return 1


def run_batch(
    folder: Path,
    *,
    size: int,
    quality: int,
    skip_existing: bool,
) -> int:
    all_images = discover_images(folder)
    image_paths = [
        image_path
        for image_path in all_images
        if not is_thumbnail_source(image_path)
    ]

    if not image_paths:
        report_error(
            f"No se encontraron imágenes en {folder.resolve()}",
            hint="Comprueba la ruta y que haya ficheros jpg, png, bmp, webp o tif.",
        )
        return 1

    subfolder_count = count_subfolders(folder, image_paths)
    print(f"Escaneando carpeta: {folder}")
    print(f"Encontradas {len(image_paths)} imágenes en {subfolder_count} subcarpetas")
    print(f"Thumbnail: {size}x{size}, calidad JPEG {quality}")

    processed = 0
    skipped = 0
    failures: list[tuple[Path, str]] = []
    file_entries: list[dict] = []

    progress = tqdm(image_paths, desc="Thumbnails", unit="img")
    for image_path in progress:
        relative_path = image_path.relative_to(folder)
        thumbnail_path = companion_thumbnail_path(image_path)

        if skip_existing and thumbnail_path.exists():
            skipped += 1
            progress.set_postfix_str(f"{relative_path.name} [saltada]", refresh=False)
            continue

        try:
            result = create_thumbnail(image_path, size=size, quality=quality)
            processed += 1
            file_entries.append(build_file_summary_entry(folder, result))
            progress.set_postfix_str(
                f"{relative_path.name} ({result.thumbnail_bytes:,} B)",
                refresh=False,
            )
        except Exception as exc:
            failures.append((relative_path, str(exc)))
            progress.set_postfix_str(f"{relative_path.name} [error]", refresh=False)

    print("\n=== Resumen batch ===")
    print(f"  Carpeta:       {folder}")
    print(f"  Procesadas:    {processed}")
    if skip_existing:
        print(f"  Saltadas:      {skipped}  (--skip-existing)")
    print(f"  Fallidas:      {len(failures)}")
    if file_entries:
        total_saved = sum(
            entry["source_bytes"] - entry["thumbnail_bytes"] for entry in file_entries
        )
        print(f"  Bytes ahorrados: {total_saved:,}")

    try:
        summary_path = write_thumbnail_summary(
            folder,
            size=size,
            quality=quality,
            processed=processed,
            skipped=skipped,
            failures=failures,
            file_entries=file_entries,
        )
        print(f"  Resumen JSON:  {summary_path}")
    except OSError as exc:
        report_error(
            f"No se pudo escribir el resumen en {folder / SUMMARY_FILENAME}: {exc}",
            hint="Comprueba permisos de escritura en la carpeta raíz del batch.",
        )
        return 1

    if failures:
        print("\nFallos:")
        for path, message in failures:
            print(f"  - {path}: {message}")
        return 1

    return 0


def main() -> int:
    try:
        args = parse_args()
    except SystemExit:
        raise
    except Exception as exc:
        report_error(
            f"No se pudieron interpretar los parámetros de entrada: {exc}",
            hint="Ejecuta: python thumbnail.py --help",
        )
        return 2

    if args.batch:
        return run_batch(
            args.batch,
            size=args.size,
            quality=args.quality,
            skip_existing=args.skip_existing,
        )

    return run_single(
        args.image,
        size=args.size,
        quality=args.quality,
    )


if __name__ == "__main__":
    raise SystemExit(main())
