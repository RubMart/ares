# -*- coding: utf-8 -*-
"""Regenerate figures 4.2 (tile) and 4.5 (detections overlay) from a valid Madrid tile."""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw

SRC = Path(r"D:\TFM\madrid_orto_2024_sur\tiles16\16\32091\24688.png")
OUT_IMAGES = Path(r"D:\TFM\ares\doc\.images")
OUT_FIGURES = Path(r"D:\TFM\ares\doc\memtech\figures")
PREVIEW_SIZE = 960
MAX_BOXES = 55


def load_detections(path: Path) -> list[dict]:
    data = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    if isinstance(data.get("detections"), list):
        return data["detections"]
    for value in data.values():
        if (
            isinstance(value, list)
            and value
            and isinstance(value[0], dict)
            and "bbox" in value[0]
        ):
            return value
    return []


def to_rgb(image: Image.Image) -> Image.Image:
    if image.mode == "RGBA":
        background = Image.new("RGB", image.size, (255, 255, 255))
        background.paste(image, mask=image.split()[-1])
        return background
    return image.convert("RGB")


def bbox_xyxy(det: dict) -> tuple[float, float, float, float] | None:
    bbox = det.get("bbox")
    if isinstance(bbox, dict):
        return float(bbox["x1"]), float(bbox["y1"]), float(bbox["x2"]), float(bbox["y2"])
    if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
        return float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])
    return None


def color_for(class_name: str) -> str:
    name = class_name.lower()
    mapping = {
        "car": "#00E5FF",
        "small vehicle": "#00BCD4",
        "van": "#76FF03",
        "bus": "#FFEA00",
        "truck": "#FF9100",
        "large vehicle": "#FF6D00",
        "building": "#FF9100",
        "swimming": "#2979FF",
        "pool": "#2979FF",
        "solar": "#E040FB",
        "panel": "#E040FB",
    }
    for key, color in mapping.items():
        if key in name:
            return color
    return "#00E5FF"


def luma_stats(path: Path) -> str:
    gray = Image.open(path).convert("L").resize((32, 32))
    pixels = list(gray.getdata())
    return (
        f"{path.name}: {path.stat().st_size} B, "
        f"luma={sum(pixels)/len(pixels):.1f}, range={min(pixels)}-{max(pixels)}"
    )


def main() -> None:
    OUT_IMAGES.mkdir(parents=True, exist_ok=True)
    OUT_FIGURES.mkdir(parents=True, exist_ok=True)

    image = to_rgb(Image.open(SRC))
    detections = load_detections(SRC)
    scale = PREVIEW_SIZE / image.size[0]
    preview = image.resize((PREVIEW_SIZE, PREVIEW_SIZE), Image.Resampling.LANCZOS)

    preview_jpg = OUT_IMAGES / "ares_tile_z16_preview.jpg"
    preview_fig = OUT_FIGURES / "ares_tile_z16_preview.jpg"
    preview.save(preview_jpg, "JPEG", quality=90, optimize=True, subsampling=0)
    preview.save(preview_fig, "JPEG", quality=88, optimize=True, subsampling=0)

    ranked = sorted(
        detections,
        key=lambda d: float(d.get("confidence") or 0.0),
        reverse=True,
    )
    overlay = preview.copy()
    draw = ImageDraw.Draw(overlay)
    drawn = 0
    for det in ranked:
        if drawn >= MAX_BOXES:
            break
        coords = bbox_xyxy(det)
        if coords is None:
            continue
        x1, y1, x2, y2 = [v * scale for v in coords]
        if x2 < x1:
            x1, x2 = x2, x1
        if y2 < y1:
            y1, y2 = y2, y1
        if (x2 - x1) < 3 or (y2 - y1) < 3:
            continue
        color = color_for(str(det.get("class_name") or "obj"))
        for width in range(3):
            draw.rectangle([x1 - width, y1 - width, x2 + width, y2 + width], outline=color)
        drawn += 1

    overlay_jpg = OUT_IMAGES / "ares_detections_overlay.jpg"
    overlay_fig = OUT_FIGURES / "ares_detections_overlay.jpg"
    overlay.save(overlay_jpg, "JPEG", quality=90, optimize=True, subsampling=0)
    overlay.save(overlay_fig, "JPEG", quality=88, optimize=True, subsampling=0)

    print(f"source={SRC}")
    print(f"detections={len(detections)} drawn={drawn}")
    print(luma_stats(preview_fig))
    print(luma_stats(overlay_fig))


if __name__ == "__main__":
    main()
