# models — pesos YOLO (y caché CLIP)

Carpeta local de **pesos de detección** usados por el pipeline offline (`tools/detect.py`). Los `.pt` **no se versionan** (están en `.gitignore`); se descargan la primera vez que se ejecuta la inferencia.

También puede contener la caché local de CLIP (`clip-vit-base-patch32/`), usada por `tools/embed.py` y por la API.

Detalle del pipeline: [`tools/README.md`](../tools/README.md). Catálogo de búsqueda (sinónimos ES/EN → `clase_yolo`): [`api/infrastructure/ai/yolo_class_catalog.py`](../api/infrastructure/ai/yolo_class_catalog.py).

## Stack activo (`--all-models`)

Definido en `CONFIGURED_MODELS` de [`tools/detect.py`](../tools/detect.py). Cada detección lleva `source_model` con el alias del peso.

| Alias / fichero | Especialización | Origen | Inferencia por defecto (`imgsz`, `conf`) |
|-----------------|-----------------|--------|------------------------------------------|
| `visdrone-yolov11s` | Vehículos y objetos pequeños (vista drone) | Hugging Face [`dronefreak/visdrone-yolov11s`](https://huggingface.co/dronefreak/visdrone-yolov11s) → `models/visdrone-yolov11s.pt` | 1280, 0.25 |
| `yolo-remote-sensing-photovoltaic` | Paneles solares (y edificios en el mismo peso) | Hugging Face [`agademer/yolo-remote-sensing-photovoltaic`](https://huggingface.co/agademer/yolo-remote-sensing-photovoltaic) → `models/yolo-remote-sensing-photovoltaic.pt` | 1280, 0.25 |
| `building-detector` | Huellas de edificios (segmentación) | Hugging Face [`keremberke/yolov8s-building-segmentation`](https://huggingface.co/keremberke/yolov8s-building-segmentation) → `models/building-detector.pt` | 1280, 0.35 |
| `swimming-pool-detector` | Piscinas | Hugging Face [`mozilla-ai/swimming-pool-detector`](https://huggingface.co/mozilla-ai/swimming-pool-detector) → `models/swimming-pool-detector.pt` | 1280, 0.25 |
| `yolo11m-obb.pt` | Objetos rotados (DOTA OBB): deportes, rotondas, vehículos, etc. | Ultralytics oficial → `models/yolo11m-obb.pt` | 1280, 0.25 |

```powershell
cd tools
python detect.py --batch <tiles>/ --all-models --skip-existing
```

---

## Clases por modelo

Nombres exactos que escribe YOLO en `class_name` del JSON (leídos de los pesos locales).

### 1. `visdrone-yolov11s` — VisDrone (AABB)

**Para qué:** detección densa de tráfico y personas en ortofoto / vista cenital u oblicua tipo drone. Es el peso por defecto si no se pasa `--model` ni `--all-models`.

| `class_id` | `class_name` |
|------------|--------------|
| 0 | `pedestrian` |
| 1 | `people` |
| 2 | `bicycle` |
| 3 | `car` |
| 4 | `van` |
| 5 | `truck` |
| 6 | `tricycle` |
| 7 | `awning-tricycle` |
| 8 | `bus` |
| 9 | `motor` |
| 10 | `others` |

En el catálogo de la API, las consultas de vehículos suelen mapear a `car`, `van`, `truck`, `bus`, `motor` (y también a clases DOTA `small vehicle` / `large vehicle` cuando vienen del OBB).

### 2. `yolo-remote-sensing-photovoltaic` — paneles solares (AABB)

**Para qué:** especialista de teledetección en instalaciones fotovoltaicas (textura / geometría de arrays).

| `class_id` | `class_name` |
|------------|--------------|
| 0 | `building` |
| 1 | `photovoltaic panel` |

La búsqueda de «paneles solares» usa `photovoltaic panel`. La clase `building` de este peso coexiste con `Building` del detector de edificios.

### 3. `building-detector` — edificios (segmentación → footprint)

**Para qué:** huellas de edificaciones. Umbral de confianza más alto (0.35) para reducir falsos positivos.

| `class_id` | `class_name` |
|------------|--------------|
| 0 | `Building` |

### 4. `swimming-pool-detector` — piscinas (AABB)

**Para qué:** clase minoritaria fácil de confundir con agua o sombras; peso dedicado.

| `class_id` | `class_name` |
|------------|--------------|
| 0 | `swimming_pool` |

Nota: el OBB DOTA también puede emitir `swimming pool` (con espacio). El catálogo de la API acepta ambas formas.

### 5. `yolo11m-obb.pt` — DOTA OBB (cajas orientadas)

**Para qué:** entidades alargadas o rotadas respecto al tile (campos deportivos, rotondas, vehículos en vista aérea, etc.). Además de `bbox`, las detecciones incluyen polígono OBB (`obb` / `obb3857`).

| `class_id` | `class_name` |
|------------|--------------|
| 0 | `plane` |
| 1 | `ship` |
| 2 | `storage tank` |
| 3 | `baseball diamond` |
| 4 | `tennis court` |
| 5 | `basketball court` |
| 6 | `ground track field` |
| 7 | `harbor` |
| 8 | `bridge` |
| 9 | `large vehicle` |
| 10 | `small vehicle` |
| 11 | `helicopter` |
| 12 | `roundabout` |
| 13 | `soccer ball field` |
| 14 | `swimming pool` |

En el producto actual, el catálogo de búsqueda destaca sobre todo `soccer ball field`, `basketball court`, `roundabout`, `small vehicle` y `large vehicle` (más el puente con piscinas / vehículos de otros pesos).

---

## Otros alias disponibles (no entran en `--all-models`)

Se pueden pedir a mano con `--model`:

| Alias | Notas |
|-------|--------|
| `visdrone-yolov11n` / `m` / `l` | Variantes VisDrone (nano / medium / large) en Hugging Face |
| `yolo11n-obb.pt` / `yolo11s-obb.pt` | DOTA OBB más ligeros (mismas 15 clases que `yolo11m-obb.pt`) |

---

## CLIP (caché en esta carpeta)

No es un detector YOLO. `embed.py` y la API usan **CLIP ViT-B/32** (`clip-ViT-B-32` / `openai/clip-vit-base-patch32`) para embeddings de imagen (offline) y de texto (online). La caché local típica es `models/clip-vit-base-patch32/`.

---

## Descarga

La primera ejecución de `detect.py` con un alias conocido descarga el peso a `models/<alias>.pt` (HF) o `models/<nombre>.pt` (Ultralytics). No hace falta copiar pesos a mano salvo que se quiera pre-cachear offline.
