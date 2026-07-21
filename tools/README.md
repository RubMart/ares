# tools — pipeline de detección e indexación

Scripts CLI para pasar de **tiles XYZ** (ortofoto / gdal2tiles) a filas en PostgreSQL (**PostGIS** + **pgvector**).

Guía extremo a extremo (COG, publicación HTTP, `gdal2tiles` z=16, YOLO, CLIP, SQL): [`doc/preparacion-de-datos.md`](../doc/preparacion-de-datos.md).  
Pesos y clases YOLO: [`models/README.md`](../models/README.md).  
Carga en BD: [`db/README.md`](../db/README.md).

Índice del monorepo: [`README.md`](../README.md).

---

## Índice

1. [Flujo](#flujo)
2. [Requisitos](#requisitos)
3. [Instalación de dependencias](#instalación-de-dependencias)
4. [Convenciones comunes](#convenciones-comunes)
5. [Scripts](#scripts)
   - [`detect.py`](#detectpy)
   - [`embed.py`](#embedpy)
   - [`thumbnail.py`](#thumbnailpy)
   - [`embed2psql.py`](#embed2psqlpy)
   - [`visualize.py`](#visualizepy)
   - [`utils.py`](#utilspy)
6. [Pipeline recomendado (batch)](#pipeline-recomendado-batch)
7. [Salidas y rutas por defecto](#salidas-y-rutas-por-defecto)
8. [Problemas frecuentes](#problemas-frecuentes)

---

## Flujo

```
tiles …/z/x/y.png
        │
        ├─► thumbnail.py  (opcional)  →  {stem}_thumb.jpg
        │
        ▼
   detect.py  →  {stem}.json           detecciones YOLO (+ bbox3857 en tiles Mercator)
        │
        ▼
   embed.py   →  {stem}_emb.json       embeddings CLIP (512-d, L2)
        │
        ▼
 embed2psql.py →  *_schema.sql / *_data.sql
        │
        ▼
   psql -f …  →  tablas + catálogo en PostgreSQL
```

`visualize.py` abre una GUI PyQt6 para revisar detecciones; **no** forma parte del indexado.

Orden obligatorio para indexar: **detect → embed → embed2psql**. Los thumbnails pueden generarse en paralelo o en cualquier momento respecto a YOLO/CLIP.

Sin rutas de tile `…/z/x/y.ext`, `detect.py` no calcula geometrías EPSG:3857 y `embed2psql.py` no puede construir un `tile_id` válido.

---

## Requisitos

| Componente | Uso |
|------------|-----|
| **Python 3.11+** | Scripts de esta carpeta |
| **PyTorch** | Inferencia YOLO (`detect.py`) y CLIP (`embed.py`) |
| **ultralytics** | YOLO v8/v11 (AABB y OBB) |
| Paquetes de [`requirements.txt`](requirements.txt) | OpenCV, Hugging Face Hub, transformers/CLIP, Pillow, pyproj, tqdm, PyQt6 |
| GPU (opcional) | Acelera `detect.py` y `embed.py`; CPU funciona |
| **GDAL** (fuera de Python) | COG + `gdal2tiles` — ver guía de preparación de datos |
| **PostgreSQL** + PostGIS + pgvector | Destino del SQL generado |
| Red (primera vez) | Descarga de pesos YOLO (HF/Ultralytics) y del modelo CLIP |

Los `.pt` y la caché CLIP viven en `<repo>/models/` (no se versionan).

---

## Instalación de dependencias

Trabaja siempre desde `tools/` (o activa el entorno y llama a los scripts con ruta relativa).

### Opción A — `venv` + pip (recomendada en Windows)

```powershell
cd D:\TFM\ares\tools
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip

# Dependencias del repo
pip install -r requirements.txt

# PyTorch + Ultralytics (elige CPU o CUDA según tu máquina)
# CPU:
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install ultralytics

# GPU CUDA 12.x (ejemplo; consulta https://pytorch.org/get-started/locally/):
# pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
# pip install ultralytics
```

Comprobar:

```powershell
python -c "import torch; import ultralytics; import cv2; print('OK', torch.__version__, torch.cuda.is_available())"
python detect.py --help
```

Desactivar el entorno: `deactivate`.

### Opción B — Conda / Miniconda / Mamba

Útil si prefieres gestionar CUDA/OpenCV vía conda-forge.

```powershell
cd D:\TFM\ares\tools

# Entorno nuevo (ajusta python=3.11 o 3.12)
conda create -n ares-tools python=3.11 -y
conda activate ares-tools

# PyTorch: CPU
conda install pytorch torchvision cpuonly -c pytorch -y

# PyTorch: GPU (ejemplo CUDA 12.4; revisa la matriz oficial de PyTorch/conda)
# conda install pytorch torchvision pytorch-cuda=12.4 -c pytorch -c nvidia -y

# Resto con pip (alineado a requirements.txt)
pip install -r requirements.txt
pip install ultralytics
```

Alternativa más “conda-first” (versiones pueden diferir de `requirements.txt`):

```powershell
conda activate ares-tools
conda install -c conda-forge opencv pillow tqdm pyproj transformers huggingface_hub -y
pip install ultralytics PyQt6
```

Comprobar igual que en venv. Desactivar: `conda deactivate`.

### Notas de instalación

- `torch` y `ultralytics` **no** están pinados en `requirements.txt` a propósito: la rueda de PyTorch depende de CPU/CUDA/plataforma.
- Primera ejecución de `detect.py` / `embed.py`: descarga pesos a `models/` (puede tardar y necesita red).
- En PowerShell, si la política de ejecución bloquea `Activate.ps1`:

  ```powershell
  Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
  ```

---

## Convenciones comunes

- Ejecuta los scripts con el **cwd en `tools/`** o como `python tools/<script>.py` desde la raíz del repo (`utils` se resuelve porque Python añade el directorio del script a `sys.path`).
- Extensiones de imagen reconocidas: `.jpg`, `.jpeg`, `.png`, `.bmp`, `.webp`, `.tif`, `.tiff`.
- Modo **batch** (`--batch CARPETA`): recorre la carpeta de forma recursiva.
- `--skip-existing`: no reprocesa si ya existe el companion de salida (JSON, `_emb.json` o `_thumb.jpg`).
- En batch, cada script escribe un resumen en la raíz de la carpeta procesada (`detection_summary.json`, `embedding_summary.json`, etc.).
- Ayuda detallada: `python <script>.py --help`.

Ficheros companion junto a cada tile:

| Fichero | Origen |
|---------|--------|
| `{stem}.json` | `detect.py` |
| `{stem}_emb.json` | `embed.py` |
| `{stem}_thumb.jpg` | `thumbnail.py` |

Ejemplo con layout gdal2tiles:

```text
tiles16/16/32101/24711.png
tiles16/16/32101/24711.json
tiles16/16/32101/24711_emb.json
tiles16/16/32101/24711_thumb.jpg
```

---

## Scripts

### `detect.py`

Inferencia YOLO sobre una imagen o un árbol de tiles. Escribe un JSON con el mismo stem junto a la imagen. Cada detección incluye `source_model`; las OBB añaden polígono orientado; en tiles Mercator `…/z/x/y` se añade `bbox3857` (EPSG:3857).

#### Uso

```powershell
# Una imagen
python detect.py path\to\tile.png
python detect.py path\to\tile.png --all-models

# Batch (stack completo del proyecto)
python detect.py --batch D:\TFM\data_madrid\tiles16\ --all-models --skip-existing

# Un solo modelo / varios a mano
python detect.py --batch tiles16\ --model visdrone-yolov11s
python detect.py --batch tiles16\ --model visdrone-yolov11s --model swimming-pool-detector
```

#### Opciones

| Opción | Descripción | Default |
|--------|-------------|---------|
| `image` | Imagen de entrada (obligatorio si no hay `--batch`) | — |
| `--batch CARPETA` | Procesa recursivamente todas las imágenes | — |
| `--skip-existing` | Omite imágenes que ya tienen JSON | off |
| `--all-models` | Ejecuta el stack configurado en el proyecto | off |
| `--model MODEL` | Modelo YOLO (repetible). No combinar con `--all-models` | `visdrone-yolov11s` |
| `--conf CONF` | Umbral de confianza ∈ [0, 1] | `0.25` (o por modelo con `--all-models`) |
| `--imgsz SIZE` | Tamaño de inferencia (px) | `640` (o por modelo con `--all-models`) |

Con `--all-models` **sin** `--conf` ni `--imgsz`, se aplican ajustes pensados para ortofoto ~2048×2048:

| Modelo | `imgsz` | `conf` | Especialización |
|--------|---------|--------|-----------------|
| `visdrone-yolov11s` | 1280 | 0.25 | Vehículos / objetos pequeños |
| `yolo-remote-sensing-photovoltaic` | 1280 | 0.25 | Paneles solares |
| `building-detector` | 1280 | 0.35 | Edificios |
| `swimming-pool-detector` | 1280 | 0.25 | Piscinas |
| `yolo11m-obb.pt` | 1280 | 0.25 | DOTA OBB (deportes, rotondas, …) |

Otros alias solo con `--model`: `visdrone-yolov11n` / `m` / `l`, `yolo11n-obb.pt`, `yolo11s-obb.pt`. Detalle de clases: [`models/README.md`](../models/README.md).

#### Salida

- `{imagen}.json` companion.
- En batch: `detection_summary.json` en la raíz de `--batch`.
- Pesos cacheados en `<repo>/models/<alias>.pt`.

---

### `embed.py`

Recorta cada detección del JSON YOLO, embebe el crop con **CLIP ViT-B/32** y escribe `{stem}_emb.json` (vectores 512-d normalizados L2). La geometría **no** se duplica: `embed2psql.py` la lee del JSON de detecciones.

#### Uso

```powershell
# Acepta imagen o JSON de detecciones
python embed.py tiles16\16\32101\24711.png
python embed.py tiles16\16\32101\24711.json

python embed.py --batch D:\TFM\data_madrid\tiles16\ --skip-existing
```

#### Opciones

| Opción | Descripción | Default |
|--------|-------------|---------|
| `input` | Imagen o JSON de detecciones (salvo `--batch`) | — |
| `--batch CARPETA` | Procesa imágenes que ya tienen JSON YOLO | — |
| `--skip-existing` | Omite si ya existe `_emb.json` | off |
| `--model MODEL` | Modelo CLIP en Hugging Face | `openai/clip-vit-base-patch32` (alias `clip-ViT-B-32`) |
| `--min-conf CONF` | Filtra detecciones por confianza mínima | `0` |
| `--classes LISTA` | Filtra por `class_name` separados por comas | todas |
| `--source-model M` | Filtra por `source_model` del JSON YOLO | todos |
| `--padding PX` | Píxeles extra alrededor del bbox antes del crop | `0` |
| `--batch-size N` | Lote de inferencia CLIP | `16` |

Ejemplos con filtros:

```powershell
python embed.py --batch tiles16\ --min-conf 0.5 --classes car,Building
python embed.py --batch tiles16\ --source-model visdrone-yolov11s --batch-size 32 --padding 4
```

#### Salida

- `{stem}_emb.json` junto a la imagen / JSON.
- Caché CLIP típica: `models/clip-vit-base-patch32/`.
- En batch: `embedding_summary.json`.

---

### `thumbnail.py`

Genera JPEG cuadrados (`*_thumb.jpg`) para previsualización / transmisión rápida. **Opcional** respecto al indexado SQL.

#### Uso

```powershell
python thumbnail.py tiles16\16\32101\24711.png
python thumbnail.py --batch D:\TFM\data_madrid\tiles16\ --skip-existing
```

#### Opciones

| Opción | Descripción | Default |
|--------|-------------|---------|
| `image` | Imagen de entrada (salvo `--batch`) | — |
| `--batch CARPETA` | Procesa recursivamente | — |
| `--skip-existing` | Omite si ya existe `_thumb.jpg` | off |
| `--size N` | Lado del cuadrado (px) | `512` |
| `--quality N` | Calidad JPEG 1–100 | `85` |

```powershell
python thumbnail.py --batch tiles16\ --size 512 --quality 75
```

#### Salida

- `{stem}_thumb.jpg` (no reprocesa ficheros cuyo stem ya termina en `_thumb`).
- En batch: `thumbnail_summary.json`.

---

### `embed2psql.py`

Lee `*_emb.json` + JSON YOLO companion y genera SQL para:

1. Tabla catálogo (`detecciones_catalogo` por defecto).
2. Tabla de capa (`--layer`): `embedding vector(512)`, `geom` EPSG:3857, índices GIST / HNSW.

No escribe en la BD: solo genera ficheros; la carga es con `psql` (u otro cliente).

#### Uso

```powershell
# Obligatorio: --layer y (--cog-path o --cog-url)
python embed2psql.py `
  --layer madrid_detections_example `
  --cog-path D:\TFM\cog_madrid\madrid_recortada_cog.tif `
  --batch D:\TFM\data_madrid\tiles16\

# Un solo fichero _emb.json
python embed2psql.py `
  --layer madrid_detections_example `
  --cog-path D:\TFM\cog_madrid\madrid_recortada_cog.tif `
  tiles16\16\32101\24711_emb.json
```

#### Opciones

| Opción | Descripción | Default |
|--------|-------------|---------|
| `--layer NOMBRE` | Nombre de tabla/capa PostgreSQL (`[A-Za-z_][A-Za-z0-9_]*`) | **obligatorio** |
| `--cog-path RUTA` | COG local (bbox EPSG:3857 desde geotags; recomendado) | — |
| `--cog-url URL` | URL remota del COG (alternativa / complemento) | — |
| `input` | Un `*_emb.json` (si no hay `--batch`) | — |
| `--batch CARPETA` | Todos los `*_emb.json` recursivos | — |
| `--output-dir DIR` | Carpeta de salida SQL | raíz del repo (`ares/`) |
| `--insert-batch-size N` | Filas por sentencia `INSERT` | `50` |
| `--min-conf CONF` | Filtra embeddings por confianza | `0` |
| `--classes LISTA` | Filtra por `class_name` | todas |
| `--source-model M` | Filtra por modelo detector | todos |
| `--strict` | Falla si falta geometría EPSG:3857 | off |
| `--catalog-table NOMBRE` | Nombre de la tabla catálogo | `detecciones_catalogo` |

Bbox del catálogo:

- Preferente: geotags del COG (`--cog-path`) → envelope 3857.
- Fallback: rango mapml / unión de tiles procesados (puede alinearse a la malla XYZ y desplazarse ligeramente).
- Solo `--cog-url`: unión de tiles procesados; la URL se guarda en el catálogo.

#### Salida (en `--output-dir`)

| Fichero | Contenido |
|---------|-----------|
| `{catalog}_schema.sql` | `CREATE TABLE` catálogo + GIST |
| `{layer}_schema.sql` | Tabla de detecciones + índices |
| `{catalog}_data.sql` | `INSERT` de la capa en el catálogo |
| `{layer}_data.sql` | `INSERT` de filas (lotes) |
| En batch: `embed2psql_summary.json` en la carpeta `--batch` | Resumen |

#### Carga en PostgreSQL

Orden típico (ajusta usuario, BD y puerto; Compose de `db/` suele usar host **7432**):

```powershell
# Extensiones (una vez)
psql -U postgres -d detecciones -c "CREATE EXTENSION IF NOT EXISTS postgis;"
psql -U postgres -d detecciones -c "CREATE EXTENSION IF NOT EXISTS vector;"

# Schema → datos de capa → catálogo
psql -U postgres -d detecciones -f D:\TFM\ares\detecciones_catalogo_schema.sql
psql -U postgres -d detecciones -f D:\TFM\ares\madrid_detections_example_schema.sql
psql -U postgres -d detecciones -f D:\TFM\ares\madrid_detections_example_data.sql
psql -U postgres -d detecciones -f D:\TFM\ares\detecciones_catalogo_data.sql
```

Con Docker Compose de [`db/`](../db/):

```powershell
$env:PGPASSWORD = "password"
psql -h localhost -p 7432 -U user -d embedding_db -f ...
```

Alinea `DATABASE_URL` de la API con la BD donde cargues el SQL.

---

### `visualize.py`

Visor local PyQt6: muestra la imagen, dibuja detecciones del JSON companion y permite activar/desactivar clases en un árbol lateral.

#### Uso

```powershell
python visualize.py samples\calle.jpg
python visualize.py D:\TFM\data_madrid\tiles16\
```

#### Opciones

| Opción | Descripción |
|--------|-------------|
| `path` | Imagen **o** carpeta con imágenes (**obligatorio**) |

Requisito: debe existir `{stem}.json` generado por `detect.py`.

No tiene modo batch con flags extra; si `path` es carpeta, lista las imágenes disponibles en la GUI.

---

### `utils.py`

Biblioteca compartida (no es un CLI): descubrimiento de imágenes, rutas companion, georreferenciación gdal2tiles → EPSG:3857, crops, literales pgvector, bbox del COG, etc. Importada por el resto de scripts.

---

## Pipeline recomendado (batch)

Sustituye rutas por las tuyas. Entorno activado (`venv` o `conda`).

```powershell
cd D:\TFM\ares\tools

$TILES = "D:\TFM\data_madrid\tiles16"
$COG   = "D:\TFM\cog_madrid\madrid_recortada_cog.tif"
$LAYER = "madrid_detections_example"
$SQLOUT = "D:\TFM\ares\sql_out"

# 1) Detección (stack completo)
python detect.py --batch $TILES --all-models --skip-existing

# 2) Embeddings CLIP
python embed.py --batch $TILES --skip-existing

# 3) Thumbnails (opcional)
python thumbnail.py --batch $TILES --skip-existing

# 4) SQL
python embed2psql.py `
  --layer $LAYER `
  --cog-path $COG `
  --batch $TILES `
  --output-dir $SQLOUT `
  --strict

# 5) Carga (ejemplo nativo)
psql -U postgres -d detecciones -f "$SQLOUT\detecciones_catalogo_schema.sql"
psql -U postgres -d detecciones -f "$SQLOUT\${LAYER}_schema.sql"
psql -U postgres -d detecciones -f "$SQLOUT\${LAYER}_data.sql"
psql -U postgres -d detecciones -f "$SQLOUT\detecciones_catalogo_data.sql"
```

Revisión cualitativa entre (1) y (2):

```powershell
python visualize.py $TILES
```

---

## Salidas y rutas por defecto

| Qué | Dónde |
|-----|--------|
| Pesos YOLO | `<repo>/models/<alias>.pt` |
| Caché CLIP | `<repo>/models/clip-vit-base-patch32/` |
| Companion JSON / emb / thumb | Junto a cada tile |
| SQL de `embed2psql.py` | Raíz del repo, o `--output-dir` |
| Summaries batch | Raíz de la carpeta `--batch` |

No versionar: `models/*.pt`, `data/`, `runs/`, salidas SQL de prueba, `.venv/`, entornos conda.

---

## Problemas frecuentes

| Síntoma | Causa habitual | Qué hacer |
|---------|----------------|-----------|
| `ModuleNotFoundError: torch` / `ultralytics` | Solo se instaló `requirements.txt` | Instalar PyTorch + ultralytics (venv o conda) |
| Sin `bbox3857` / `embed2psql --strict` falla | Tiles fuera de layout `z/x/y` | Regenerar con `gdal2tiles` y re-ejecutar `detect.py` |
| Primera corrida muy lenta | Descarga de pesos | Esperar; o pre-cachear modelos en `models/` |
| GPU no usada | Build CPU de torch | Reinstalar torch con índice CUDA adecuado |
| API sin resultados | BD/capa distinta | Verificar `DATABASE_URL` y que la capa esté en el catálogo |
| PyQt6 no arranca | Entorno headless / display | Usar máquina con GUI; `visualize.py` no es necesario para indexar |

Más detalle de COG/tiles y checklist E2E: [`doc/preparacion-de-datos.md`](../doc/preparacion-de-datos.md).
