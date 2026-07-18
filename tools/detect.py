#!/usr/bin/env python3
"""Detect objects in aerial or urban images using YOLO and save results to JSON."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path

import cv2
import torch
from huggingface_hub import hf_hub_download
from tqdm import tqdm
from ultralytics import YOLO

from utils import (
    companion_json_path,
    discover_images,
    enrich_detections_with_epsg3857,
)



SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
MODELS_DIR = REPO_ROOT / "models"

# Modelos que se ejecutan con --all-models (stack activo del proyecto).
CONFIGURED_MODELS = [
    "visdrone-yolov11s",  # coches
    "yolo-remote-sensing-photovoltaic",  # paneles solares
    "building-detector",  # edificios
    "swimming-pool-detector",  # piscinas
    "yolo11m-obb.pt",  # campos deportivos (DOTA OBB)
]

# Ajustes por modelo para --all-models (imgsz, conf). Ortofotos 2048×2048.
MODEL_INFERENCE_DEFAULTS: dict[str, tuple[int, float]] = {
    "visdrone-yolov11s": (1280, 0.25),
    "yolo-remote-sensing-photovoltaic": (1280, 0.25),
    "building-detector": (1280, 0.35),
    "swimming-pool-detector": (1280, 0.25),
    "yolo11m-obb.pt": (1280, 0.25),
}

DEFAULT_MODELS = ["visdrone-yolov11s"]
DEFAULT_CONFIDENCE = 0.25
DEFAULT_IMGSZ = 640
SUMMARY_FILENAME = "detection_summary.json"

# Modelos en Hugging Face. Se guardan en models/<alias>.pt la primera vez.
HF_MODELS: dict[str, tuple[str, str]] = {
    "visdrone-yolov11s": ("dronefreak/visdrone-yolov11s", "best.pt"),
    "visdrone-yolov11n": ("dronefreak/visdrone-yolov11n", "best.pt"),
    "visdrone-yolov11m": ("dronefreak/visdrone-yolov11m", "best.pt"),
    "visdrone-yolov11l": ("dronefreak/visdrone-yolov11l", "best.pt"),
    "yolo-remote-sensing-photovoltaic": (
        "agademer/yolo-remote-sensing-photovoltaic",
        "yolo-remote-sensing-photovoltaic-v8l-solar-farms-and-cities-v20260331-detect-1000_epochs.pt",
    ),
    "swimming-pool-detector": ("mozilla-ai/swimming-pool-detector", "model.pt"),
    "building-detector": ("keremberke/yolov8s-building-segmentation", "best.pt"),
}

# Modelos Ultralytics oficiales. Se guardan en models/<nombre>.pt la primera vez.
# DOTA OBB: campos deportivos, pistas, piscinas, etc. en imágenes aéreas.
ULTRALYTICS_MODELS = {
    "yolo11n-obb.pt",
    "yolo11s-obb.pt",
    "yolo11m-obb.pt",
}

EPILOG = f"""
Parámetros (modo imagen única):
  image          Ruta a la imagen de entrada (jpg, png, bmp, webp, tif, ...)

Parámetros (modo batch):
  --batch CARPETA   Procesa recursivamente todas las imágenes de la carpeta
  --skip-existing   Salta imágenes que ya tienen un JSON asociado

Parámetros opcionales:
  --all-models   Ejecuta todos los modelos configurados en el proyecto
  --model MODEL  Modelo YOLO (repetible). Por defecto: visdrone-yolov11s
  --conf CONF    Umbral de confianza entre 0 y 1 (por defecto: {DEFAULT_CONFIDENCE})
  --imgsz SIZE   Tamaño de inferencia en píxeles (por defecto: {DEFAULT_IMGSZ})

Modelos en --all-models (stack completo):
  visdrone-yolov11s              coches
  yolo-remote-sensing-photovoltaic  paneles solares
  building-detector              edificios
  swimming-pool-detector         piscinas
  yolo11m-obb.pt                 campos deportivos (DOTA OBB)

Con --all-models sin --conf ni --imgsz se aplican ajustes por modelo (ortofoto 2048).

Otros alias disponibles manualmente con --model:
  visdrone-yolov11n / m / l
  yolo-remote-sensing-photovoltaic
  swimming-pool-detector
  building-detector  (edificios; recomendado --imgsz 1280 --conf 0.35)
  yolo11n-obb.pt / yolo11s-obb.pt / yolo11m-obb.pt  (DOTA; deportes en ortofoto)

Salida:
  Genera un JSON con el mismo nombre y en la misma carpeta que la imagen.
  Cada detección incluye source_model. Las OBB incluyen además el polígono orientado.
  En tiles gdal2tiles Mercator (ruta .../z/x/y.png) se añade bbox3857 en EPSG:3857.
  En modo batch, genera detection_summary.json en la raíz de la carpeta indicada.

Ejemplos:
  python detect.py tiles20/395440.png
  python detect.py tiles20/395440.png --all-models
  python detect.py --batch pruebas/ --all-models
  python detect.py --batch pruebas/ --all-models --skip-existing
  python detect.py --batch tiles20/
  python detect.py --batch tiles20/ --skip-existing
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


def resolve_device() -> str:
    if torch.cuda.is_available():
        return "0"
    return "cpu"


def ensure_local_hf_weights(alias: str, repo_id: str, filename: str) -> Path:
    """Return project-local weights path, downloading once into models/ if needed."""
    local_path = MODELS_DIR / f"{alias}.pt"
    if local_path.exists():
        return local_path

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    downloaded_path = Path(hf_hub_download(repo_id=repo_id, filename=filename))
    shutil.copy2(downloaded_path, local_path)
    print(f"Modelo descargado y guardado en: {local_path}")
    return local_path


def ensure_local_ultralytics_weights(model_filename: str) -> Path:
    """Download Ultralytics weights once and store them under models/."""
    local_path = MODELS_DIR / model_filename
    if local_path.exists():
        return local_path

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    downloaded = YOLO(model_filename)
    source_candidates = [
        Path(model_filename),
        Path(downloaded.ckpt_path) if getattr(downloaded, "ckpt_path", None) else None,
    ]
    for candidate in source_candidates:
        if candidate and candidate.is_file():
            shutil.copy2(candidate, local_path)
            print(f"Modelo descargado y guardado en: {local_path}")
            return local_path

    raise FileNotFoundError(
        f"No se pudo guardar localmente el modelo Ultralytics: {model_filename}"
    )


def resolve_model_weights(model_name: str) -> tuple[str, str]:
    """Return local weights path and the model label to store in JSON."""
    alias = model_name.lower()
    if alias in HF_MODELS:
        repo_id, filename = HF_MODELS[alias]
        local_path = ensure_local_hf_weights(alias, repo_id, filename)
        return str(local_path.resolve()), alias

    normalized = Path(model_name).name.lower()
    if normalized in {name.lower() for name in ULTRALYTICS_MODELS}:
        local_path = ensure_local_ultralytics_weights(Path(model_name).name)
        return str(local_path.resolve()), Path(model_name).name

    weights_path = Path(model_name)
    if weights_path.is_file():
        return str(weights_path.resolve()), weights_path.name

    if weights_path.is_absolute() or weights_path.suffix == ".pt":
        raise FileNotFoundError(f"No se encontró el modelo: {model_name}")

    return model_name, model_name


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Detecta objetos en imágenes urbanas o aéreas con YOLO "
            "y guarda las detecciones en un fichero JSON."
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
        help="Procesa recursivamente todas las imágenes de la carpeta indicada.",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="En modo batch, salta imágenes que ya tienen un JSON asociado.",
    )
    parser.add_argument(
        "--all-models",
        action="store_true",
        help=(
            "Ejecuta todos los modelos configurados: "
            + ", ".join(CONFIGURED_MODELS)
        ),
    )
    parser.add_argument(
        "--model",
        action="append",
        dest="models",
        metavar="MODEL",
        help=(
            "Modelo YOLO especializado. Repite la opción para combinar varios modelos "
            f"(por defecto: {DEFAULT_MODELS[0]}). No combinar con --all-models."
        ),
    )
    parser.add_argument(
        "--conf",
        type=confidence_value,
        default=None,
        metavar="CONF",
        help=(
            f"Umbral de confianza entre 0 y 1 (por defecto: {DEFAULT_CONFIDENCE}, "
            "o por modelo con --all-models)."
        ),
    )
    parser.add_argument(
        "--imgsz",
        type=int,
        default=None,
        metavar="SIZE",
        help=(
            f"Tamaño de inferencia en píxeles (por defecto: {DEFAULT_IMGSZ}, "
            "o por modelo con --all-models)."
        ),
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

    if args.all_models and args.models:
        parser.error("No combines --all-models con --model. Usa solo una de las dos opciones.")

    if args.all_models:
        args.models = list(CONFIGURED_MODELS)
    elif not args.models:
        args.models = list(DEFAULT_MODELS)

    args.use_per_model_defaults = (
        args.all_models and args.conf is None and args.imgsz is None
    )
    args.conf = DEFAULT_CONFIDENCE if args.conf is None else args.conf
    args.imgsz = DEFAULT_IMGSZ if args.imgsz is None else args.imgsz
    return args


def resolve_model_inference(
    model_name: str,
    image_size: int,
    confidence: float,
    use_per_model_defaults: bool,
) -> tuple[int, float]:
    if use_per_model_defaults and model_name in MODEL_INFERENCE_DEFAULTS:
        return MODEL_INFERENCE_DEFAULTS[model_name]
    return image_size, confidence


def validate_image(image_path: Path) -> tuple[int, int]:
    if not image_path.exists():
        raise FileNotFoundError(
            f"No se encontró la imagen: {image_path.resolve()}"
        )

    if not image_path.is_file():
        raise ValueError(
            f"La ruta no es un fichero de imagen: {image_path.resolve()}"
        )

    image = cv2.imread(str(image_path))
    if image is None:
        raise ValueError(
            f"No se pudo leer la imagen: {image_path.resolve()}\n"
            "Comprueba que el formato sea compatible (jpg, png, bmp, webp, tif, ...)."
        )

    height, width = image.shape[:2]
    return width, height


def bbox_from_xyxy(xyxy: list[float]) -> dict[str, float]:
    return {
        "x1": round(xyxy[0], 2),
        "y1": round(xyxy[1], 2),
        "x2": round(xyxy[2], 2),
        "y2": round(xyxy[3], 2),
    }


def extract_detections(result, model_label: str) -> list[dict]:
    detections: list[dict] = []
    names = result.names

    if result.boxes is not None:
        for box in result.boxes:
            class_id = int(box.cls.item())
            xyxy = box.xyxy[0].tolist()
            detections.append(
                {
                    "class_id": class_id,
                    "class_name": names[class_id],
                    "confidence": round(float(box.conf.item()), 4),
                    "source_model": model_label,
                    "bbox_type": "axis",
                    "bbox": bbox_from_xyxy(xyxy),
                }
            )

    if result.obb is not None:
        for box in result.obb:
            class_id = int(box.cls.item())
            xyxy = box.xyxy[0].tolist()
            detection = {
                "class_id": class_id,
                "class_name": names[class_id],
                "confidence": round(float(box.conf.item()), 4),
                "source_model": model_label,
                "bbox_type": "obb",
                "bbox": bbox_from_xyxy(xyxy),
            }
            corners = box.xyxyxyxy[0].tolist()
            detection["obb"] = {
                "points": [
                    {"x": round(point[0], 2), "y": round(point[1], 2)}
                    for point in corners
                ]
            }
            detections.append(detection)

    return detections


def load_models(model_names: list[str]) -> list[tuple[YOLO, str]]:
    """Load all models once and return (model, label) pairs."""
    loaded: list[tuple[YOLO, str]] = []
    for model_name in model_names:
        weights_path, model_label = resolve_model_weights(model_name)
        loaded.append((YOLO(weights_path), model_label))
    return loaded


def detect_with_loaded_model(
    model: YOLO,
    model_label: str,
    image_path: Path,
    confidence: float,
    image_size: int,
) -> list[dict]:
    results = model.predict(
        source=str(image_path),
        conf=confidence,
        imgsz=image_size,
        device=resolve_device(),
        verbose=False,
    )
    return extract_detections(results[0], model_label)


def run_detection(
    image_path: Path,
    loaded_models: list[tuple[YOLO, str]],
    model_names: list[str],
    confidence: float,
    image_size: int,
    use_per_model_defaults: bool = False,
) -> dict:
    width, height = validate_image(image_path)

    all_detections: list[dict] = []
    model_settings: dict[str, dict[str, float | int]] = {}
    for model, model_label in loaded_models:
        model_imgsz, model_conf = resolve_model_inference(
            model_label,
            image_size,
            confidence,
            use_per_model_defaults,
        )
        model_settings[model_label] = {
            "inference_size": model_imgsz,
            "confidence_threshold": model_conf,
        }
        model_detections = detect_with_loaded_model(
            model,
            model_label,
            image_path,
            model_conf,
            model_imgsz,
        )
        all_detections.extend(model_detections)

    all_detections = enrich_detections_with_epsg3857(
        all_detections,
        image_path,
        width,
        height,
    )

    payload: dict = {
        "source_image": str(image_path.resolve()),
        "models": model_names,
        "confidence_threshold": confidence,
        "inference_size": image_size,
        "model_settings": model_settings,
        "image_size": {"width": width, "height": height},
        "detections": all_detections,
    }

    return payload


def print_summary(detections: list[dict], models: list[str], output_path: Path) -> None:
    counts = Counter(detection["class_name"] for detection in detections)
    model_counts = Counter(detection.get("source_model", "unknown") for detection in detections)

    print(f"Saved {len(detections)} detections to {output_path}")
    if len(models) == 1:
        print(f"Model: {models[0]}")
    else:
        print(f"Models: {', '.join(models)}")
    if model_counts:
        print("Detections by model:")
        for model_name, count in sorted(model_counts.items()):
            print(f"  - {model_name}: {count}")
    if counts:
        print("Detections by class:")
        for class_name, count in sorted(counts.items()):
            print(f"  - {class_name}: {count}")
    else:
        print("No objects detected above the confidence threshold.")


def count_subfolders(folder: Path, image_paths: list[Path]) -> int:
    subfolders = {path.parent for path in image_paths if path.parent != folder}
    return len(subfolders)


def build_model_settings(
    model_names: list[str],
    confidence: float,
    image_size: int,
    use_per_model_defaults: bool,
) -> dict[str, dict[str, float | int]]:
    settings: dict[str, dict[str, float | int]] = {}
    for model_name in model_names:
        model_imgsz, model_conf = resolve_model_inference(
            model_name,
            image_size,
            confidence,
            use_per_model_defaults,
        )
        settings[model_name] = {
            "inference_size": model_imgsz,
            "confidence_threshold": model_conf,
        }
    return settings


def build_detection_summary(
    folder: Path,
    image_paths: list[Path],
    model_names: list[str],
    confidence: float,
    image_size: int,
    use_per_model_defaults: bool,
    processed: int,
    skipped: int,
    failures: list[tuple[Path, str]],
) -> dict:
    class_counts: Counter[str] = Counter()
    class_counts_by_model: dict[str, Counter[str]] = defaultdict(Counter)
    model_counts: Counter[str] = Counter()
    images_with_json = 0
    images_with_detections = 0

    for image_path in image_paths:
        json_path = companion_json_path(image_path)
        if not json_path.exists():
            continue

        try:
            payload = json.loads(json_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        images_with_json += 1
        detections = payload.get("detections", [])
        if detections:
            images_with_detections += 1

        for detection in detections:
            if not isinstance(detection, dict):
                continue
            class_name = str(detection.get("class_name", "unknown"))
            source_model = str(detection.get("source_model", "unknown"))
            class_counts[class_name] += 1
            class_counts_by_model[source_model][class_name] += 1
            model_counts[source_model] += 1

    return {
        "source_folder": str(folder.resolve()),
        "models": model_names,
        "confidence_threshold": confidence,
        "inference_size": image_size,
        "use_per_model_defaults": use_per_model_defaults,
        "model_settings": build_model_settings(
            model_names,
            confidence,
            image_size,
            use_per_model_defaults,
        ),
        "run": {
            "processed": processed,
            "skipped": skipped,
            "failed": len(failures),
            "total_images": len(image_paths),
        },
        "images_with_json": images_with_json,
        "images_with_detections": images_with_detections,
        "total_detections": sum(class_counts.values()),
        "detections_by_model": dict(sorted(model_counts.items())),
        "classes": dict(sorted(class_counts.items())),
        "classes_by_model": {
            model_name: dict(sorted(counts.items()))
            for model_name, counts in sorted(class_counts_by_model.items())
        },
        "failures": [
            {"image": str(path), "error": message}
            for path, message in failures
        ],
    }


def write_detection_summary(
    folder: Path,
    image_paths: list[Path],
    model_names: list[str],
    confidence: float,
    image_size: int,
    use_per_model_defaults: bool,
    processed: int,
    skipped: int,
    failures: list[tuple[Path, str]],
) -> Path:
    summary_path = folder / SUMMARY_FILENAME
    summary = build_detection_summary(
        folder,
        image_paths,
        model_names,
        confidence,
        image_size,
        use_per_model_defaults,
        processed,
        skipped,
        failures,
    )
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return summary_path


def run_batch(
    folder: Path,
    model_names: list[str],
    confidence: float,
    image_size: int,
    skip_existing: bool,
    use_per_model_defaults: bool = False,
) -> int:
    image_paths = discover_images(folder)
    if not image_paths:
        report_error(
            f"No se encontraron imágenes en {folder.resolve()}",
            hint="Comprueba la ruta y que haya ficheros jpg, png, bmp, webp o tif.",
        )
        return 1

    subfolder_count = count_subfolders(folder, image_paths)
    print(f"Escaneando carpeta: {folder}")
    print(f"Encontradas {len(image_paths)} imágenes en {subfolder_count} subcarpetas")
    print(f"Modelos: {', '.join(model_names)}")
    if use_per_model_defaults:
        print("Inferencia: ajustes por modelo (MODEL_INFERENCE_DEFAULTS)")
        for model_name in model_names:
            imgsz, conf = resolve_model_inference(
                model_name,
                image_size,
                confidence,
                use_per_model_defaults,
            )
            print(f"  - {model_name}: imgsz={imgsz}, conf={conf}")
    else:
        print(f"Inferencia: imgsz={image_size}, conf={confidence}")
    print(f"Dispositivo: {resolve_device()}")
    print("Precargando modelos...")

    try:
        loaded_models = load_models(model_names)
    except Exception as exc:
        report_error(
            f"No se pudieron cargar los modelos: {exc}",
            hint="Verifica que los modelos existan en models/ o puedan descargarse.",
        )
        return 1

    processed = 0
    skipped = 0
    total_detections = 0
    failures: list[tuple[Path, str]] = []

    progress = tqdm(image_paths, desc="Detectando", unit="img")
    for image_path in progress:
        output_path = companion_json_path(image_path)
        relative_path = image_path.relative_to(folder)

        if skip_existing and output_path.exists():
            skipped += 1
            progress.set_postfix_str(f"{relative_path.name} [saltada]", refresh=False)
            continue

        try:
            payload = run_detection(
                image_path,
                loaded_models,
                model_names,
                confidence,
                image_size,
                use_per_model_defaults,
            )
            output_path.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            detection_count = len(payload["detections"])
            processed += 1
            total_detections += detection_count
            progress.set_postfix_str(
                f"{relative_path.name}, {detection_count} det",
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
    print(f"  Detecciones:   {total_detections}")

    try:
        summary_path = write_detection_summary(
            folder,
            image_paths,
            model_names,
            confidence,
            image_size,
            use_per_model_defaults,
            processed,
            skipped,
            failures,
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


def run_single(
    image_path: Path,
    model_names: list[str],
    confidence: float,
    image_size: int,
    use_per_model_defaults: bool = False,
) -> int:
    output_path = companion_json_path(image_path)

    try:
        loaded_models = load_models(model_names)
        payload = run_detection(
            image_path,
            loaded_models,
            model_names,
            confidence,
            image_size,
            use_per_model_defaults,
        )
        output_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print_summary(payload["detections"], payload["models"], output_path)
        return 0
    except FileNotFoundError as exc:
        report_error(
            str(exc),
            hint="Indica la ruta completa a la imagen. Ejemplo: python detect.py samples/calle.jpg",
        )
        return 1
    except ValueError as exc:
        report_error(
            str(exc),
            hint="Usa otra imagen o comprueba que el fichero no esté corrupto.",
        )
        return 1
    except OSError as exc:
        report_error(
            f"No se pudo escribir el JSON en {output_path.resolve()}: {exc}",
            hint="Comprueba permisos de escritura en la carpeta de la imagen.",
        )
        return 1
    except Exception as exc:
        error_text = str(exc).lower()
        if "model" in error_text or "weight" in error_text or ".pt" in error_text:
            hint = (
                f"Verifica que los modelos {model_names} existan en models/ o puedan descargarse. "
                "Prueba con: --model visdrone-yolov11s"
            )
        else:
            hint = "Revisa la imagen, el modelo y que el entorno Conda con YOLO esté activado."

        report_error(f"Fallo durante la detección: {exc}", hint=hint)
        return 1


def main() -> int:
    try:
        args = parse_args()
    except SystemExit:
        raise
    except Exception as exc:
        report_error(
            f"No se pudieron interpretar los parámetros de entrada: {exc}",
            hint="Ejecuta: python detect.py --help",
        )
        return 2

    if args.batch:
        return run_batch(
            args.batch,
            args.models,
            args.conf,
            args.imgsz,
            args.skip_existing,
            args.use_per_model_defaults,
        )

    return run_single(
        args.image,
        args.models,
        args.conf,
        args.imgsz,
        args.use_per_model_defaults,
    )


if __name__ == "__main__":
    raise SystemExit(main())
