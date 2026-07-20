#!/usr/bin/env python3
"""Generate CLIP embeddings for YOLO detection crops and save them to JSON."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import cv2
import torch
from PIL import Image
from tqdm import tqdm
from transformers import CLIPModel, CLIPProcessor

from utils import (
    companion_embedding_json_path,
    companion_json_path,
    crop_detection_axis,
    discover_images,
    load_detection_json,
    resolve_source_image_path,
)

DEFAULT_MODEL = "openai/clip-vit-base-patch32"
CLIP_MODEL_ALIASES = frozenset({DEFAULT_MODEL, "clip-ViT-B-32"})
DEFAULT_BATCH_SIZE = 16
DEFAULT_PADDING = 0
SUMMARY_FILENAME = "embedding_summary.json"

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
DEFAULT_CLIP_LOCAL_DIR = REPO_ROOT / "models" / "clip-vit-base-patch32"

EPILOG = f"""
Parámetros (modo entrada única):
  input          Ruta a una imagen o a su JSON de detecciones

Parámetros (modo batch):
  --batch CARPETA   Procesa recursivamente imágenes con JSON de detecciones
  --skip-existing   Salta imágenes que ya tienen un fichero _emb.json

Parámetros opcionales:
  --model MODEL       Modelo CLIP en HuggingFace (por defecto: {DEFAULT_MODEL})
  --min-conf CONF     Filtra detecciones por confianza mínima (por defecto: 0)
  --classes LISTA     Filtra por class_name separados por comas (ej: car,Building)
  --source-model M    Filtra por source_model del JSON de detecciones
  --padding PX        Píxeles extra alrededor del bbox antes del recorte
  --batch-size N      Tamaño de lote para inferencia CLIP (por defecto: {DEFAULT_BATCH_SIZE})

Salida:
  Genera un JSON con sufijo _emb junto a la imagen o JSON de detecciones.
  Ejemplo: 24711.png / 24711.json -> 24711_emb.json
  En modo batch, genera {SUMMARY_FILENAME} en la raíz de la carpeta indicada.

Ejemplos:
  python embed.py pruebas/tiles16/16/32101/24711.png
  python embed.py pruebas/tiles16/16/32101/24711.json
  python embed.py --batch pruebas/tiles16/ --skip-existing
  python embed.py --batch pruebas/tiles16/ --min-conf 0.5 --classes car,Building
  python embed.py --batch pruebas/tiles16/ --batch-size 32 --padding 4
"""


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


def non_negative_int(raw_value: str) -> int:
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"'{raw_value}' no es un entero válido."
        ) from exc

    if value < 0:
        raise argparse.ArgumentTypeError(
            f"El valor no puede ser negativo (recibido: {value})."
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


def resolve_device() -> torch.device:
    if torch.cuda.is_available():
        return torch.device("cuda:0")
    return torch.device("cpu")


def resolve_detection_json_path(input_path: Path) -> Path:
    suffix = input_path.suffix.lower()
    if suffix == ".json":
        return input_path
    if suffix in {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}:
        return companion_json_path(input_path)
    raise ValueError(
        f"La entrada debe ser una imagen o un JSON de detecciones: {input_path.resolve()}"
    )


def resolve_output_base_path(input_path: Path, detection_json_path: Path) -> Path:
    suffix = input_path.suffix.lower()
    if suffix == ".json":
        return detection_json_path
    return input_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Genera embeddings CLIP para los recortes de las detecciones YOLO "
            "y guarda un JSON _emb por imagen."
        ),
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "input",
        type=Path,
        nargs="?",
        default=None,
        metavar="input",
        help="Ruta a una imagen o JSON de detecciones (obligatorio salvo con --batch).",
    )
    parser.add_argument(
        "--batch",
        type=Path,
        metavar="CARPETA",
        help="Procesa recursivamente imágenes con JSON de detecciones en la carpeta.",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="En modo batch, salta imágenes que ya tienen un fichero _emb.json.",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        metavar="MODEL",
        help=f"Modelo CLIP en HuggingFace (por defecto: {DEFAULT_MODEL}).",
    )
    parser.add_argument(
        "--min-conf",
        type=confidence_value,
        default=0.0,
        metavar="CONF",
        help="Filtra detecciones con confianza menor que este umbral (por defecto: 0).",
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
        help="Filtra por source_model del JSON de detecciones.",
    )
    parser.add_argument(
        "--padding",
        type=non_negative_int,
        default=DEFAULT_PADDING,
        metavar="PX",
        help=f"Píxeles extra alrededor del bbox (por defecto: {DEFAULT_PADDING}).",
    )
    parser.add_argument(
        "--batch-size",
        type=positive_int,
        default=DEFAULT_BATCH_SIZE,
        metavar="N",
        help=f"Tamaño de lote para inferencia CLIP (por defecto: {DEFAULT_BATCH_SIZE}).",
    )

    if len(sys.argv) == 1:
        parser.print_help()
        print(
            "\nFalta el parámetro obligatorio: input o --batch CARPETA",
            file=sys.stderr,
        )
        raise SystemExit(2)

    args = parser.parse_args()

    if args.batch and args.input:
        parser.error("No combines --batch con el argumento input. Usa solo uno de los dos modos.")

    if not args.batch and args.input is None:
        parser.error("Indica una imagen/JSON o usa --batch CARPETA.")

    return args


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


def resolve_clip_model_source(model_name: str) -> str:
    """Resuelve ruta local o id HF; evita tokens HF inválidos en repos públicos."""
    as_path = Path(model_name)
    if _is_clip_dir_ready(as_path):
        return str(as_path.resolve())

    if model_name not in CLIP_MODEL_ALIASES:
        return model_name

    if _is_clip_dir_ready(DEFAULT_CLIP_LOCAL_DIR):
        return str(DEFAULT_CLIP_LOCAL_DIR.resolve())

    cached = find_hf_hub_snapshot(DEFAULT_MODEL)
    if cached is not None:
        return str(cached)

    DEFAULT_CLIP_LOCAL_DIR.parent.mkdir(parents=True, exist_ok=True)
    from huggingface_hub import snapshot_download

    # token=False: repos públicos no deben usar un token local inválido/caducado
    # (HF responde a veces "Repository Not Found" + OAuth signature failed).
    snapshot_download(
        repo_id=DEFAULT_MODEL,
        local_dir=str(DEFAULT_CLIP_LOCAL_DIR),
        token=False,
    )
    return str(DEFAULT_CLIP_LOCAL_DIR.resolve())


def load_clip_model(model_name: str, device: torch.device) -> tuple[CLIPModel, CLIPProcessor]:
    source = resolve_clip_model_source(model_name)
    # token=False evita 401 por token OAuth/local corrupto al cargar un modelo público.
    processor = CLIPProcessor.from_pretrained(source, token=False)
    model = CLIPModel.from_pretrained(source, token=False)
    model.to(device)
    model.eval()
    return model, processor


def filter_detections(
    detections: list[dict],
    *,
    min_confidence: float,
    classes: list[str] | None,
    source_model: str | None,
) -> list[tuple[int, dict]]:
    class_filter = {name.lower() for name in classes} if classes else None
    filtered: list[tuple[int, dict]] = []

    for index, detection in enumerate(detections):
        confidence = detection.get("confidence")
        if not isinstance(confidence, (int, float)) or confidence < min_confidence:
            continue

        if class_filter is not None:
            class_name = detection.get("class_name")
            if not isinstance(class_name, str) or class_name.lower() not in class_filter:
                continue

        if source_model is not None:
            model_name = detection.get("source_model")
            if model_name != source_model:
                continue

        filtered.append((index, detection))

    return filtered


def bgr_to_pil(image_bgr) -> Image.Image:
    image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    return Image.fromarray(image_rgb)


def encode_crops(
    model: CLIPModel,
    processor: CLIPProcessor,
    crops_bgr: list,
    *,
    device: torch.device,
    batch_size: int,
) -> list[list[float]]:
    if not crops_bgr:
        return []

    embeddings: list[list[float]] = []

    for start in range(0, len(crops_bgr), batch_size):
        batch_crops = crops_bgr[start : start + batch_size]
        pil_images = [bgr_to_pil(crop) for crop in batch_crops]
        inputs = processor(images=pil_images, return_tensors="pt", padding=True)
        pixel_values = inputs["pixel_values"].to(device)

        with torch.no_grad():
            vision_outputs = model.vision_model(pixel_values=pixel_values)
            features = model.visual_projection(vision_outputs.pooler_output)
            features = features / features.norm(dim=-1, keepdim=True)

        for vector in features.cpu().tolist():
            embeddings.append(vector)

    return embeddings


def build_embedding_record(
    detection_index: int,
    detection: dict,
    embedding: list[float],
) -> dict:
    record = {
        "detection_index": detection_index,
        "class_name": detection.get("class_name"),
        "class_id": detection.get("class_id"),
        "confidence": detection.get("confidence"),
        "source_model": detection.get("source_model"),
        "bbox_type": detection.get("bbox_type"),
        "bbox": detection.get("bbox"),
        "embedding": embedding,
    }
    return record


def run_embedding(
    detection_json_path: Path,
    *,
    model: CLIPModel,
    processor: CLIPProcessor,
    device: torch.device,
    model_name: str,
    min_confidence: float,
    classes: list[str] | None,
    source_model: str | None,
    padding: int,
    batch_size: int,
) -> dict:
    payload = load_detection_json(detection_json_path)
    source_image_path = resolve_source_image_path(detection_json_path, payload)

    if not source_image_path.exists():
        raise FileNotFoundError(
            f"No se encontró la imagen fuente: {source_image_path.resolve()}"
        )

    image_bgr = cv2.imread(str(source_image_path))
    if image_bgr is None:
        raise ValueError(
            f"No se pudo leer la imagen fuente: {source_image_path.resolve()}"
        )

    filtered = filter_detections(
        payload["detections"],
        min_confidence=min_confidence,
        classes=classes,
        source_model=source_model,
    )

    crops_bgr = []
    valid_items: list[tuple[int, dict]] = []
    for detection_index, detection in filtered:
        crop = crop_detection_axis(image_bgr, detection, padding=padding)
        if crop is None:
            continue
        crops_bgr.append(crop)
        valid_items.append((detection_index, detection))

    vectors = encode_crops(
        model,
        processor,
        crops_bgr,
        device=device,
        batch_size=batch_size,
    )

    embedding_dim = model.config.projection_dim
    embeddings = [
        build_embedding_record(detection_index, detection, vector)
        for (detection_index, detection), vector in zip(valid_items, vectors, strict=True)
    ]

    return {
        "source_image": str(source_image_path.resolve()),
        "source_detection_json": str(detection_json_path.resolve()),
        "embedding_model": model_name,
        "embedding_dim": embedding_dim,
        "padding_px": padding,
        "filters": {
            "min_confidence": min_confidence,
            "classes": classes,
            "source_model": source_model,
        },
        "embedding_count": len(embeddings),
        "embeddings": embeddings,
    }


def print_summary(payload: dict, output_path: Path) -> None:
    print(f"Embeddings guardados en: {output_path.resolve()}")
    print(f"  Modelo:      {payload['embedding_model']}")
    print(f"  Dimensión:   {payload['embedding_dim']}")
    print(f"  Embeddings:  {payload['embedding_count']}")


def count_subfolders(folder: Path, image_paths: list[Path]) -> int:
    subfolders = {path.parent for path in image_paths if path.parent != folder}
    return len(subfolders)


def build_embedding_summary(
    folder: Path,
    image_paths: list[Path],
    model_name: str,
    embedding_dim: int,
    processed: int,
    skipped: int,
    failures: list[tuple[Path, str]],
    total_embeddings: int,
    embeddings_by_class: Counter[str],
) -> dict:
    return {
        "source_folder": str(folder.resolve()),
        "embedding_model": model_name,
        "embedding_dim": embedding_dim,
        "run": {
            "processed": processed,
            "skipped": skipped,
            "failed": len(failures),
            "total_images": len(image_paths),
        },
        "total_embeddings": total_embeddings,
        "embeddings_by_class": dict(sorted(embeddings_by_class.items())),
        "failures": [
            {"path": str((folder / relative_path).resolve()), "error": message}
            for relative_path, message in failures
        ],
    }


def write_embedding_summary(
    folder: Path,
    image_paths: list[Path],
    model_name: str,
    embedding_dim: int,
    processed: int,
    skipped: int,
    failures: list[tuple[Path, str]],
    total_embeddings: int,
    embeddings_by_class: Counter[str],
) -> Path:
    summary_path = folder / SUMMARY_FILENAME
    summary = build_embedding_summary(
        folder,
        image_paths,
        model_name,
        embedding_dim,
        processed,
        skipped,
        failures,
        total_embeddings,
        embeddings_by_class,
    )
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return summary_path


def run_single(
    input_path: Path,
    *,
    model_name: str,
    min_confidence: float,
    classes: list[str] | None,
    source_model: str | None,
    padding: int,
    batch_size: int,
) -> int:
    try:
        detection_json_path = resolve_detection_json_path(input_path)
        output_base_path = resolve_output_base_path(input_path, detection_json_path)
        output_path = companion_embedding_json_path(output_base_path)

        device = resolve_device()
        model, processor = load_clip_model(model_name, device)
        payload = run_embedding(
            detection_json_path,
            model=model,
            processor=processor,
            device=device,
            model_name=model_name,
            min_confidence=min_confidence,
            classes=classes,
            source_model=source_model,
            padding=padding,
            batch_size=batch_size,
        )
        output_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print_summary(payload, output_path)
        return 0
    except FileNotFoundError as exc:
        report_error(
            str(exc),
            hint=(
                "Genera primero el JSON de detecciones con detect.py. "
                "Ejemplo: python detect.py tiles20/395440.png"
            ),
        )
        return 1
    except ValueError as exc:
        report_error(
            str(exc),
            hint="Comprueba que la imagen y el JSON de detecciones sean válidos.",
        )
        return 1
    except OSError as exc:
        report_error(
            f"No se pudo escribir el JSON de embeddings: {exc}",
            hint="Comprueba permisos de escritura en la carpeta de salida.",
        )
        return 1
    except Exception as exc:
        report_error(
            f"Fallo durante la generación de embeddings: {exc}",
            hint="Revisa el JSON, la imagen fuente y que transformers/torch estén instalados.",
        )
        return 1


def run_batch(
    folder: Path,
    *,
    model_name: str,
    min_confidence: float,
    classes: list[str] | None,
    source_model: str | None,
    padding: int,
    batch_size: int,
    skip_existing: bool,
) -> int:
    all_images = discover_images(folder)
    image_paths = [
        image_path
        for image_path in all_images
        if companion_json_path(image_path).exists()
    ]

    if not image_paths:
        report_error(
            f"No se encontraron imágenes con JSON de detecciones en {folder.resolve()}",
            hint=(
                "Ejecuta primero detect.py en la carpeta. "
                "Ejemplo: python detect.py --batch pruebas/tiles16/"
            ),
        )
        return 1

    subfolder_count = count_subfolders(folder, image_paths)
    device = resolve_device()

    print(f"Escaneando carpeta: {folder}")
    print(f"Encontradas {len(image_paths)} imágenes con JSON en {subfolder_count} subcarpetas")
    print(f"Modelo CLIP: {model_name}")
    print(f"Inferencia: batch_size={batch_size}, padding={padding}")
    print(f"Dispositivo: {device}")
    print("Precargando modelo CLIP...")

    try:
        model, processor = load_clip_model(model_name, device)
    except Exception as exc:
        report_error(
            f"No se pudo cargar el modelo CLIP: {exc}",
            hint=(
                "Verifica transformers y el nombre del modelo. "
                "Si el error es 401/OAuth de Hugging Face, borra el token inválido "
                "(huggingface-cli logout) o usa la caché local en models/clip-vit-base-patch32."
            ),
        )
        return 1

    embedding_dim = model.config.projection_dim
    processed = 0
    skipped = 0
    total_embeddings = 0
    embeddings_by_class: Counter[str] = Counter()
    failures: list[tuple[Path, str]] = []

    progress = tqdm(image_paths, desc="Embeddings", unit="img")
    for image_path in progress:
        detection_json_path = companion_json_path(image_path)
        output_path = companion_embedding_json_path(image_path)
        relative_path = image_path.relative_to(folder)

        if skip_existing and output_path.exists():
            skipped += 1
            progress.set_postfix_str(f"{relative_path.name} [saltada]", refresh=False)
            continue

        try:
            payload = run_embedding(
                detection_json_path,
                model=model,
                processor=processor,
                device=device,
                model_name=model_name,
                min_confidence=min_confidence,
                classes=classes,
                source_model=source_model,
                padding=padding,
                batch_size=batch_size,
            )
            output_path.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            embedding_count = payload["embedding_count"]
            processed += 1
            total_embeddings += embedding_count
            for item in payload["embeddings"]:
                class_name = item.get("class_name")
                if isinstance(class_name, str):
                    embeddings_by_class[class_name] += 1
            progress.set_postfix_str(
                f"{relative_path.name}, {embedding_count} emb",
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
    print(f"  Embeddings:    {total_embeddings}")

    try:
        summary_path = write_embedding_summary(
            folder,
            image_paths,
            model_name,
            embedding_dim,
            processed,
            skipped,
            failures,
            total_embeddings,
            embeddings_by_class,
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
            hint="Ejecuta: python embed.py --help",
        )
        return 2

    if args.batch:
        return run_batch(
            args.batch,
            model_name=args.model,
            min_confidence=args.min_conf,
            classes=args.classes,
            source_model=args.source_model,
            padding=args.padding,
            batch_size=args.batch_size,
            skip_existing=args.skip_existing,
        )

    return run_single(
        args.input,
        model_name=args.model,
        min_confidence=args.min_conf,
        classes=args.classes,
        source_model=args.source_model,
        padding=args.padding,
        batch_size=args.batch_size,
    )


if __name__ == "__main__":
    raise SystemExit(main())
