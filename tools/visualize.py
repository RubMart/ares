#!/usr/bin/env python3
"""Visualize YOLO detections from a companion JSON file with a class toggle tree."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

import cv2
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QScrollArea,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from utils import companion_json_path, discover_images


class DetectionValidationError(Exception):
    """Raised when the companion JSON or image data is invalid."""


EPILOG = """
Parámetros requeridos:
  path           Ruta a una imagen o a una carpeta con imágenes

Requisitos previos:
  Debe existir un JSON asociado con el mismo nombre y carpeta que la imagen.
  Ejemplo: samples/calle.jpg requiere samples/calle.json
  Genera el JSON con: python detect.py samples/calle.jpg

Ejemplos:
  python visualize.py samples/calle.jpg
  python visualize.py tiles20/
  python visualize.py D:/TFM/fotos/avenida.png
"""


def report_error(message: str, *, hint: str | None = None) -> None:
    print(f"Error: {message}", file=sys.stderr)
    if hint:
        print(f"Sugerencia: {hint}", file=sys.stderr)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Visualiza las detecciones YOLO de imágenes usando el JSON asociado. "
            "Permite activar y desactivar clases desde un árbol lateral."
        ),
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "path",
        type=Path,
        metavar="path",
        help="Ruta a una imagen o carpeta con imágenes (obligatorio).",
    )
    if len(sys.argv) == 1:
        parser.print_help()
        print(
            "\nFalta el parámetro obligatorio: path",
            file=sys.stderr,
        )
        raise SystemExit(2)

    return parser.parse_args()


def load_image_bgr(image_path: Path):
    if not image_path.exists():
        raise DetectionValidationError(
            f"No se encontró la imagen: {image_path.resolve()}"
        )

    if not image_path.is_file():
        raise DetectionValidationError(
            f"La ruta no es un fichero de imagen: {image_path.resolve()}"
        )

    image = cv2.imread(str(image_path))
    if image is None:
        raise DetectionValidationError(
            f"No se pudo leer la imagen: {image_path.resolve()}\n"
            "Comprueba que el formato sea compatible (jpg, png, bmp, webp, tif, ...)."
        )
    return image


def load_detection_payload(image_path: Path, json_path: Path) -> dict:
    if not json_path.exists():
        raise DetectionValidationError(
            f"No se encontró el JSON asociado: {json_path.resolve()}\n"
            f"Genera primero las detecciones con: python detect.py {image_path}"
        )

    try:
        payload = json.loads(json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DetectionValidationError(
            f"El fichero JSON no es válido: {json_path.resolve()}\n"
            f"Detalle del parser: {exc}"
        ) from exc
    except OSError as exc:
        raise DetectionValidationError(
            f"No se pudo leer el JSON: {json_path.resolve()}\n"
            f"Detalle: {exc}"
        ) from exc

    if not isinstance(payload, dict):
        raise DetectionValidationError(
            "El JSON debe ser un objeto en la raíz del documento."
        )

    if "detections" not in payload:
        raise DetectionValidationError(
            "El JSON no contiene el campo obligatorio 'detections'."
        )
    if not isinstance(payload["detections"], list):
        raise DetectionValidationError(
            "El campo 'detections' del JSON debe ser una lista."
        )

    image = load_image_bgr(image_path)

    image_height, image_width = image.shape[:2]
    image_size = payload.get("image_size")
    if isinstance(image_size, dict):
        expected_width = image_size.get("width")
        expected_height = image_size.get("height")
        if (
            isinstance(expected_width, int)
            and isinstance(expected_height, int)
            and (expected_width != image_width or expected_height != image_height)
        ):
            raise DetectionValidationError(
                "Las dimensiones de la imagen no coinciden con las del JSON "
                f"({image_width}x{image_height} en imagen vs "
                f"{expected_width}x{expected_height} en JSON).\n"
                "Vuelve a generar el JSON con detect.py sobre la imagen actual."
            )

    validated_detections: list[dict] = []
    for index, detection in enumerate(payload["detections"]):
        if not isinstance(detection, dict):
            raise DetectionValidationError(
                f"La detección #{index} debe ser un objeto JSON."
            )

        class_name = detection.get("class_name")
        bbox = detection.get("bbox")
        if not isinstance(class_name, str) or not class_name:
            raise DetectionValidationError(
                f"La detección #{index} no tiene un 'class_name' válido."
            )
        if not isinstance(bbox, dict):
            raise DetectionValidationError(
                f"La detección #{index} no tiene un objeto 'bbox' válido."
            )

        required_keys = ("x1", "y1", "x2", "y2")
        for key in required_keys:
            if key not in bbox or not isinstance(bbox[key], (int, float)):
                raise DetectionValidationError(
                    f"La detección #{index} requiere '{key}' numérico dentro de 'bbox'."
                )

        x1, y1, x2, y2 = float(bbox["x1"]), float(bbox["y1"]), float(bbox["x2"]), float(bbox["y2"])
        if x2 <= x1 or y2 <= y1:
            raise DetectionValidationError(
                f"La detección #{index} tiene un bbox inválido "
                f"({x1}, {y1}, {x2}, {y2})."
            )

        confidence = detection.get("confidence", 0.0)
        if not isinstance(confidence, (int, float)):
            confidence = 0.0

        source_model = detection.get("source_model")
        if source_model is not None and not isinstance(source_model, str):
            source_model = None

        validated_detections.append(
            {
                "class_name": class_name,
                "confidence": float(confidence),
                "source_model": source_model,
                "bbox": {"x1": x1, "y1": y1, "x2": x2, "y2": y2},
            }
        )

    payload["detections"] = validated_detections
    payload["_image_bgr"] = image
    return payload


def display_key(detection: dict) -> str:
    class_name = detection["class_name"]
    source_model = detection.get("source_model")
    if source_model:
        return f"{class_name} [{source_model}]"
    return class_name


def color_for_class(class_name: str) -> tuple[int, int, int]:
    digest = hashlib.md5(class_name.encode("utf-8")).hexdigest()
    return (
        int(digest[0:2], 16),
        int(digest[2:4], 16),
        int(digest[4:6], 16),
    )


def render_detections(image_bgr, detections: list[dict], enabled_classes: set[str]):
    canvas = image_bgr.copy()

    for detection in detections:
        key = display_key(detection)
        if key not in enabled_classes:
            continue

        bbox = detection["bbox"]
        x1 = int(bbox["x1"])
        y1 = int(bbox["y1"])
        x2 = int(bbox["x2"])
        y2 = int(bbox["y2"])
        color = color_for_class(key)

        cv2.rectangle(canvas, (x1, y1), (x2, y2), color, 2)
        label = f"{key} {detection['confidence']:.2f}"
        (text_width, text_height), baseline = cv2.getTextSize(
            label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1
        )
        text_top = max(y1, text_height + baseline + 4)
        cv2.rectangle(
            canvas,
            (x1, text_top - text_height - baseline - 4),
            (x1 + text_width + 4, text_top),
            color,
            -1,
        )
        cv2.putText(
            canvas,
            label,
            (x1 + 2, text_top - baseline - 2),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )

    return canvas


def bgr_to_qpixmap(image_bgr) -> QPixmap:
    image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    height, width, channels = image_rgb.shape
    bytes_per_line = channels * width
    qimage = QImage(
        image_rgb.data,
        width,
        height,
        bytes_per_line,
        QImage.Format.Format_RGB888,
    )
    return QPixmap.fromImage(qimage.copy())


def find_initial_index(image_paths: list[Path]) -> int:
    for index, image_path in enumerate(image_paths):
        if companion_json_path(image_path).exists():
            return index
    return 0


class DetectionViewer(QMainWindow):
    def __init__(self, root_path: Path, image_paths: list[Path], initial_index: int = 0):
        super().__init__()
        self.root_path = root_path
        self.image_paths = image_paths
        self.current_index = -1
        self.image_bgr = None
        self.detections: list[dict] = []
        self.enabled_classes: set[str] = set()
        self.status_message = ""

        self.resize(1200, 800)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)

        left_panel = QVBoxLayout()

        self.images_label = QLabel(f"Imágenes ({len(image_paths)})")
        left_panel.addWidget(self.images_label)

        self.image_list = QListWidget()
        self.image_list.currentRowChanged.connect(self.on_image_selected)
        left_panel.addWidget(self.image_list)

        self.classes_label = QLabel("Clases")
        left_panel.addWidget(self.classes_label)

        self.toggle_all = QCheckBox("Todas")
        self.toggle_all.setChecked(True)
        self.toggle_all.stateChanged.connect(self.on_toggle_all_changed)
        left_panel.addWidget(self.toggle_all)

        self.class_tree = QTreeWidget()
        self.class_tree.setHeaderLabels(["Clase", "Cantidad"])
        self.class_tree.itemChanged.connect(self.on_tree_item_changed)
        left_panel.addWidget(self.class_tree)

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(self.image_label)

        layout.addLayout(left_panel, 1)
        layout.addWidget(scroll_area, 4)

        self.populate_image_list()
        self.image_list.blockSignals(True)
        self.image_list.setCurrentRow(initial_index)
        self.image_list.blockSignals(False)
        self.load_image_at_index(initial_index)

    def relative_display_path(self, image_path: Path) -> str:
        try:
            return str(image_path.relative_to(self.root_path))
        except ValueError:
            return image_path.name

    def populate_image_list(self) -> None:
        self.image_list.clear()
        for image_path in self.image_paths:
            relative_path = self.relative_display_path(image_path)
            has_json = companion_json_path(image_path).exists()
            label = relative_path if has_json else f"{relative_path} (sin JSON)"
            item = QListWidgetItem(label)
            item.setToolTip(
                f"python detect.py {image_path}"
                if not has_json
                else relative_path
            )
            self.image_list.addItem(item)

    def on_image_selected(self, index: int) -> None:
        if index < 0 or index == self.current_index:
            return
        self.load_image_at_index(index)

    def load_image_at_index(self, index: int) -> None:
        if index < 0 or index >= len(self.image_paths):
            return

        image_path = self.image_paths[index]
        self.current_index = index
        relative_path = self.relative_display_path(image_path)
        json_path = companion_json_path(image_path)

        self.setWindowTitle(
            f"YOLO Visualizer - {relative_path} ({index + 1}/{len(self.image_paths)})"
        )

        try:
            payload = load_detection_payload(image_path, json_path)
            self.image_bgr = payload["_image_bgr"]
            self.detections = payload["detections"]
            self.enabled_classes = {display_key(detection) for detection in self.detections}
            self.status_message = ""
        except DetectionValidationError as exc:
            try:
                self.image_bgr = load_image_bgr(image_path)
            except DetectionValidationError:
                self.image_bgr = None
            self.detections = []
            self.enabled_classes = set()
            self.status_message = str(exc)

        self.populate_tree()
        self.refresh_image()

    def populate_tree(self) -> None:
        self.class_tree.blockSignals(True)
        self.class_tree.clear()

        grouped: dict[str, list[dict]] = defaultdict(list)
        for detection in self.detections:
            grouped[display_key(detection)].append(detection)

        for key in sorted(grouped):
            item = QTreeWidgetItem([key, str(len(grouped[key]))])
            item.setFlags(
                item.flags()
                | Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
            )
            item.setCheckState(
                0,
                Qt.CheckState.Checked
                if key in self.enabled_classes
                else Qt.CheckState.Unchecked,
            )
            self.class_tree.addTopLevelItem(item)

        self.class_tree.expandAll()
        self.class_tree.blockSignals(False)
        self.sync_toggle_all_checkbox()

    def sync_toggle_all_checkbox(self) -> None:
        self.toggle_all.blockSignals(True)
        if not self.class_tree.topLevelItemCount():
            self.toggle_all.setChecked(False)
        else:
            all_checked = all(
                self.class_tree.topLevelItem(index).checkState(0) == Qt.CheckState.Checked
                for index in range(self.class_tree.topLevelItemCount())
            )
            self.toggle_all.setChecked(all_checked)
        self.toggle_all.blockSignals(False)

    def on_toggle_all_changed(self, state: int) -> None:
        checked = state == Qt.CheckState.Checked.value
        self.class_tree.blockSignals(True)
        for index in range(self.class_tree.topLevelItemCount()):
            item = self.class_tree.topLevelItem(index)
            item.setCheckState(0, Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
        self.class_tree.blockSignals(False)
        self.update_enabled_classes_from_tree()
        self.refresh_image()

    def on_tree_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        if column != 0:
            return
        self.sync_toggle_all_checkbox()
        self.update_enabled_classes_from_tree()
        self.refresh_image()

    def update_enabled_classes_from_tree(self) -> None:
        enabled = set()
        for index in range(self.class_tree.topLevelItemCount()):
            item = self.class_tree.topLevelItem(index)
            if item.checkState(0) == Qt.CheckState.Checked:
                enabled.add(item.text(0))
        self.enabled_classes = enabled

    def refresh_image(self) -> None:
        if self.image_bgr is None:
            self.image_label.setText(self.status_message or "No se pudo cargar la imagen.")
            self.image_label.setPixmap(QPixmap())
            return

        rendered = render_detections(self.image_bgr, self.detections, self.enabled_classes)
        self.image_label.setText("")
        self.image_label.setPixmap(bgr_to_qpixmap(rendered))

        if self.status_message and not self.detections:
            self.image_label.setToolTip(self.status_message)
        else:
            self.image_label.setToolTip("")


def resolve_image_paths(path: Path) -> tuple[Path, list[Path]]:
    if not path.exists():
        raise FileNotFoundError(f"No se encontró la ruta: {path.resolve()}")

    if path.is_dir():
        image_paths = discover_images(path)
        if not image_paths:
            raise ValueError(
                f"No se encontraron imágenes en {path.resolve()}\n"
                "Comprueba que haya ficheros jpg, png, bmp, webp o tif."
            )
        return path, image_paths

    if path.is_file():
        return path.parent, [path]

    raise ValueError(f"La ruta no es un fichero ni una carpeta: {path.resolve()}")


def main() -> int:
    try:
        args = parse_args()
    except SystemExit:
        raise
    except Exception as exc:
        report_error(
            f"No se pudieron interpretar los parámetros de entrada: {exc}",
            hint="Ejecuta: python visualize.py --help",
        )
        return 2

    try:
        root_path, image_paths = resolve_image_paths(args.path)
    except (FileNotFoundError, ValueError) as exc:
        report_error(
            str(exc),
            hint="Indica una imagen o carpeta válida. Ejemplo: python visualize.py tiles20/",
        )
        return 1

    initial_index = find_initial_index(image_paths)

    try:
        app = QApplication(sys.argv)
        window = DetectionViewer(root_path, image_paths, initial_index)
        window.show()
        return app.exec()
    except Exception as exc:
        report_error(
            f"No se pudo abrir el visualizador: {exc}",
            hint=(
                "Comprueba que PyQt6 esté instalado en el entorno Conda "
                "(pip install -r requirements.txt) y que tengas entorno gráfico disponible."
            ),
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
