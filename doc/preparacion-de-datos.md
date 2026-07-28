# Preparación de datos de prueba

Guía técnica extremo a extremo para construir un **dataset de prueba de ARES** a partir de una ortofoto: Cloud Optimized GeoTIFF (COG) → publicación HTTP → tiles XYZ (nivel 16) → detección YOLO → embeddings CLIP → carga en PostgreSQL (PostGIS + pgvector).

El pipeline offline vive en [`tools/`](../tools/). Esta guía detalla **qué hace cada etapa**, **por qué** se hace así y **cómo** ejecutarlo con las herramientas del repo.

## Flujo general

```mermaid
flowchart TD
    Ortho[Ortofoto GeoTIFF]
    Cog[COG con GDAL]
    Pub[Publicación HTTP Range]
    Tiles["Tiles XYZ z=16<br/>gdal2tiles"]
    Yolo["detect.py<br/>YOLO"]
    Clip["embed.py<br/>CLIP"]
    Thumb["thumbnail.py<br/>opcional"]
    Sql["embed2psql.py<br/>SQL"]
    Db[(PostgreSQL<br/>PostGIS + pgvector)]

    Ortho --> Cog --> Pub
    Cog --> Tiles
    Tiles --> Yolo --> Clip --> Sql --> Db
    Tiles --> Thumb
    Pub -.->|cog_url en catálogo| Sql
```

Orden obligatorio para indexar:

1. Ortofoto georreferenciada → **COG**
2. (Recomendado) **Publicar** el COG con soporte `Range`
3. Generar **tiles** Web Mercator en zoom **16** (layout `z/x/y`)
4. **YOLO** → JSON de detecciones (+ `bbox3857`)
5. **CLIP** → JSON de embeddings (`*_emb.json`)
6. (Opcional) **thumbnails** 512×512
7. **SQL** + carga en la BD `detecciones`

Sin tiles en rutas `…/z/x/y.ext`, `detect.py` no puede calcular geometrías EPSG:3857 y `embed2psql.py` no puede construir un `tile_id` válido.

---

## 0. Requisitos y layout de trabajo

### Software

| Herramienta | Uso |
|-------------|-----|
| [GDAL](https://gdal.org/) ≥ 3.x | `gdalinfo`, `gdal_translate` / driver `COG`, `gdal2tiles` |
| Python 3.11+ | Scripts en `tools/` |
| PyTorch + Ultralytics | Inferencia YOLO (`detect.py`) |
| Dependencias de `tools/requirements.txt` | OpenCV, transformers/CLIP, Pillow, pyproj, tqdm, … |
| PostgreSQL 14+ | Destino del índice |
| Extensiones **PostGIS** y **pgvector** | Geometría + `vector(512)` |
| Servidor HTTP con **byte-range** | Publicar el COG (S3, MinIO, nginx, Caddy, …) |

Comprueba GDAL:

```powershell
gdalinfo --version
gdal_translate --formats | Select-String COG
```

Entorno Python del pipeline:

```powershell
cd D:\TFM\ares\tools
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
# PyTorch + ultralytics según tu GPU/CPU (ver docs Ultralytics)
pip install ultralytics torch
```

Pesos YOLO/CLIP se cachean en `<repo>/models/` (fuera de git).

### Layout de carpetas sugerido

Sustituye rutas por las tuyas; el ejemplo usa una zona de Madrid:

```text
D:\TFM\data_madrid\
├── raw\
│   └── ortofoto.tif              # entrada (cualquier CRS georreferenciado)
├── cog\
│   └── madrid_recortada_cog.tif  # COG de trabajo
└── tiles16\                      # salida gdal2tiles
    ├── 16\
    │   └── <x>\
    │       └── <y>.png
    ├── mapml.mapml               # metadatos de extensión (útil al catálogo)
    └── …
```

Tras el indexado, los companion JSON viven **junto a cada tile**:

```text
tiles16/16/32101/24711.png
tiles16/16/32101/24711.json          # detecciones YOLO
tiles16/16/32101/24711_emb.json      # embeddings CLIP
tiles16/16/32101/24711_thumb.jpg     # opcional
```

---

## 1. Inspeccionar y preparar la ortofoto

Antes de COG o tiles, confirma CRS, tamaño y que el GeoTIFF es north-up (sin rotación / GCPs raros). El código de catálogo en `utils.read_geotiff_native_envelope` asume **ModelTiepoint en píxel (0,0)** + **ModelPixelScale**, típico de un COG generado con `gdal_translate`.

```powershell
gdalinfo D:\TFM\data_madrid\raw\ortofoto.tif
```

Revisa en la salida:

- `Coordinate System` / `AUTHORITY["EPSG","…"]`
- `Origin`, `Pixel Size`
- `Size is width, height`
- Ausencia de `GEOLOCATION` / transformaciones afines no north-up

### Recorte de una AOI (recomendado para pruebas)

Una ortofoto completa a 0,25–0,5 m/px genera miles de tiles en z=16. Para un dataset de prueba, recorta un polígono o un bbox:

```powershell
# Bbox en el CRS nativo del ráster (ulx uly lrx lry)
gdal_translate `
  -projwin 440000 4475000 442000 4473000 `
  -of GTiff `
  D:\TFM\data_madrid\raw\ortofoto.tif `
  D:\TFM\data_madrid\raw\ortofoto_aoi.tif
```

O con un shapefile/geojson de máscara:

```powershell
gdalwarp -cutline aoi.geojson -crop_to_cutline `
  D:\TFM\data_madrid\raw\ortofoto.tif `
  D:\TFM\data_madrid\raw\ortofoto_aoi.tif
```

### Reproyección a Web Mercator (opcional pero coherente)

Los tiles XYZ de `gdal2tiles` y las geometrías de ARES usan **EPSG:3857**. Puedes:

- dejar el COG en el CRS nativo (p. ej. ETRS89/UTM) y dejar que `gdal2tiles` reproyecte al volar, o
- materializar ya en 3857 para depurar extents con las mismas unidades que PostGIS.

```powershell
gdalwarp -t_srs EPSG:3857 -r bilinear `
  D:\TFM\data_madrid\raw\ortofoto_aoi.tif `
  D:\TFM\data_madrid\raw\ortofoto_aoi_3857.tif
```

---

## 2. Convertir a Cloud Optimized GeoTIFF (COG)

Un COG es un GeoTIFF **teselado**, con **overviews** internas y layout que permite leer ventanas vía HTTP `Range` sin descargar el fichero entero. En ARES el COG es la referencia de capa en `detecciones_catalogo.cog_url` y la fuente preferida del **bbox** del catálogo (`cog_bbox_sql_from_path`).

### Conversión recomendada (driver `COG`)

```powershell
gdal_translate `
  -of COG `
  -co COMPRESS=DEFLATE `
  -co PREDICTOR=2 `
  -co BLOCKSIZE=512 `
  -co OVERVIEWS=IGNORE_EXISTING `
  -co BIGTIFF=IF_SAFER `
  D:\TFM\data_madrid\raw\ortofoto_aoi.tif `
  D:\TFM\data_madrid\cog\madrid_recortada_cog.tif
```

Variante con JPEG (ortofotos RGB, más ligeras; pierde lossless):

```powershell
gdal_translate `
  -of COG `
  -co COMPRESS=JPEG `
  -co QUALITY=85 `
  -co BLOCKSIZE=512 `
  -co BIGTIFF=IF_SAFER `
  D:\TFM\data_madrid\raw\ortofoto_aoi.tif `
  D:\TFM\data_madrid\cog\madrid_recortada_cog.tif
```

### Validación

```powershell
gdalinfo D:\TFM\data_madrid\cog\madrid_recortada_cog.tif
python -c "from osgeo import gdal; print(gdal.Info(r'D:\TFM\data_madrid\cog\madrid_recortada_cog.tif', format='json')['metadata'].get('IMAGE_STRUCTURE', {}))"
```

Comprueba que:

- hay **overviews** (`Overviews:` en `gdalinfo`)
- el fichero es usable como GeoTIFF estándar (los scripts leen geotags con Pillow, sin abrir todos los píxeles)

Equivalente conceptual a lo que hace el catálogo al leer el envelope:

```python
# Equivalente simplificado a utils.cog_envelope_epsg3857_from_geotiff
from pathlib import Path
from tools.utils import cog_envelope_epsg3857_from_geotiff  # desde repo root con PYTHONPATH

envelope = cog_envelope_epsg3857_from_geotiff(
    Path(r"D:\TFM\data_madrid\cog\madrid_recortada_cog.tif")
)
print(envelope)  # {"x1", "y1", "x2", "y2"} en EPSG:3857
```

Si ejecutas desde `tools/`:

```powershell
cd D:\TFM\ares\tools
python -c "from pathlib import Path; from utils import cog_envelope_epsg3857_from_geotiff; print(cog_envelope_epsg3857_from_geotiff(Path(r'D:\TFM\data_madrid\cog\madrid_recortada_cog.tif')))"
```

---

## 3. Publicar el COG online

La API/catálogo guardan una referencia (`cog_url`): ruta local o URL remota. Para un flujo realista de prueba (y para consumir el COG desde un visor o cliente HTTP), súbelo a un origen que soporte **HTTP Range** (`Accept-Ranges: bytes`). Sin Range, un cliente COG descarga el objeto completo.

### Opciones habituales

| Destino | Notas |
|---------|--------|
| **MinIO / S3 / R2** | Ideal; URLs firmadas o bucket público de solo lectura |
| **nginx / Caddy** | Sirve el `.tif` con `Range` habilitado por defecto en estáticos |
| **Python http.server** | Solo para demos locales; Range limitado / no producción |

### Ejemplo: MinIO (S3-compatible)

```powershell
# Tras configurar mc alias
mc mb local/ares-cogs
mc anonymous set download local/ares-cogs
mc cp D:\TFM\data_madrid\cog\madrid_recortada_cog.tif local/ares-cogs/madrid_recortada_cog.tif
```

URL resultante (ejemplo):

```text
http://localhost:9000/ares-cogs/madrid_recortada_cog.tif
```

### Ejemplo: nginx

```nginx
location /cogs/ {
    alias /var/www/cogs/;
    # Range está activo en static; fuerza tipo
    types { image/tiff tif tiff; }
    default_type image/tiff;
}
```

### Comprobar Range

```powershell
curl -I "http://localhost:9000/ares-cogs/madrid_recortada_cog.tif"
# Debe incluir: Accept-Ranges: bytes

curl -H "Range: bytes=0-1023" -I "http://localhost:9000/ares-cogs/madrid_recortada_cog.tif"
# Esperado: HTTP/1.1 206 Partial Content
```

Guarda la URL; la usarás en `embed2psql.py --cog-url` (o mantén `--cog-path` local para calcular el bbox y registra la URL en un segundo paso si lo necesitas). En la práctica del proyecto:

- `--cog-path` → bbox fiable desde geotags + `cog_url` = ruta absoluta local
- `--cog-url` → referencia remota; el bbox del catálogo sale de la unión de tiles procesados si no hay path local

Para datasets de prueba, **recomendación**: siempre pasa `--cog-path` al generar SQL (bbox correcto) y, si publicas, documenta la URL pública en `metadata` o sustituye `cog_url` en el SQL/`UPDATE` del catálogo.

---

## 4. Generar tiles de nivel 16 con gdal2tiles

ARES asume el layout **XYZ / Google** de `gdal2tiles`: rutas `…/<z>/<x>/<y>.png` (o jpg). `utils.parse_gdal2tiles_path` extrae `(z, x, y)` de esa ruta; con ello se calculan `bbox3857` y `tile_id = "z/x/y"`.

### Por qué zoom 16 y tiles grandes

| Parámetro | Valor usado en el proyecto | Motivo |
|-----------|----------------------------|--------|
| Zoom | **16** | Compromiso cobertura / detalle urbano (~2,4 m/px en 256 px estándar) |
| `--tilesize` | **2048** | Más contexto por tile para YOLO; `detect.py` está afinado a ortofotos 2048×2048 |
| Perfil | mercator / xyz | Alineado con EPSG:3857 y OpenLayers |

En z=16, un tile “estándar” 256×256 cubre ~150 m de lado; con `--tilesize=2048` cada fichero es un **super-tile** (8×8 tiles lógicos de 256), pero la ruta sigue siendo un único `z/x/y` en la malla XYZ. El georref de `utils.pixel_to_epsg3857` escala píxeles al tamaño estándar 256 para no romper la malla.

### Comando

```powershell
# Desde GDAL (gdal2tiles.py debe estar en PATH)
gdal2tiles.py `
  --xyz `
  --tilesize=2048 `
  --zoom=16-16 `
  --processes=4 `
  --webviewer=none `
  D:\TFM\data_madrid\cog\madrid_recortada_cog.tif `
  D:\TFM\data_madrid\tiles16
```

Notas:

- `--zoom=16-16` genera **solo** el nivel 16 (evita pirámide completa).
- `--xyz` (o perfiles equivalentes según versión GDAL) produce esquema XYZ compatible con el parser del repo.
- La carpeta de salida debe quedar con estructura `tiles16/16/<x>/<y>.png`.
- `gdal2tiles` escribe `mapml.mapml` junto a los tiles; `embed2psql` puede usarlo como **fallback** de bbox si fallan los geotags del COG.

### Verificar layout

```powershell
Get-ChildItem D:\TFM\data_madrid\tiles16\16 -Directory | Select-Object -First 3
# Ejemplo de tile esperado:
# D:\TFM\data_madrid\tiles16\16\32101\24711.png
```

Smoke test del parser del proyecto:

```powershell
cd D:\TFM\ares\tools
python -c "from pathlib import Path; from utils import build_tile_id; print(build_tile_id(Path(r'D:\TFM\data_madrid\tiles16\16\32101\24711.png')))"
# -> 16/32101/24711
```

### Volumen esperado

Aprox. tiles ≈ cobertura / (tamaño de tile en metros). Una AOI de ~2×2 km en z=16 con tilesize 2048 puede quedar en **decenas** de PNG; la misma AOI con tilesize 256 serían cientos. Empieza pequeño, mide tiempo YOLO/CLIP y escala.

---

## 5. Extraer contenidos con YOLO (`detect.py`)

Cada PNG se pasa por uno o varios modelos YOLO. La salida es un JSON companion **en la misma carpeta** que la imagen. Si la ruta es gdal2tiles, cada detección recibe `bbox3857` (y `obb3857` si aplica).

### Qué ocurre por tile (código)

```python
# Esquema de tools/detect.py → run_detection()
width, height = validate_image(image_path)

all_detections = []
for model, model_label in loaded_models:
    results = model.predict(
        source=str(image_path),
        conf=confidence,
        imgsz=image_size,
        device=resolve_device(),
        verbose=False,
    )
    all_detections.extend(extract_detections(results[0], model_label))

# Georreferenciación solo si path ~ .../z/x/y.png y tile cuadrado
all_detections = enrich_detections_with_epsg3857(
    all_detections, image_path, width, height
)

payload = {
    "source_image": str(image_path.resolve()),
    "models": model_names,
    "image_size": {"width": width, "height": height},
    "detections": all_detections,  # bbox + bbox3857 + class_name + confidence + source_model
}
# Escrito en image_path.with_suffix(".json")
```

Conversión píxel → metros (Web Mercator):

```python
# tools/utils.py (concepto)
# global_px = tile_x * 256 + pixel_x * (256 / tile_pixel_size)
# mx = global_px * meters_per_pixel - ORIGIN_SHIFT
# my = ORIGIN_SHIFT - global_py * meters_per_pixel
```

### Modelos del stack (`--all-models`)

| Alias | Enfoque |
|-------|---------|
| `visdrone-yolov11s` | Vehículos / objetos VisDrone |
| `yolo-remote-sensing-photovoltaic` | Paneles solares |
| `building-detector` | Edificios |
| `swimming-pool-detector` | Piscinas |
| `yolo11m-obb.pt` | DOTA OBB (campos deportivos, etc.) |

Con `--all-models` y tiles 2048, sin override manual se aplican `imgsz`/`conf` por modelo (p. ej. 1280 / 0.25–0.35).

### Clases de la prueba de concepto

Los pesos anteriores emiten muchas etiquetas YOLO (`class_name` en el JSON). Para la **PoC de ARES**, la búsqueda en lenguaje natural se acota a un **catálogo canónico** de familias semánticas (sinónimos ES/EN → `clase_yolo` en BD). Ese mapeo vive en [`api/infrastructure/ai/yolo_class_catalog.py`](../api/infrastructure/ai/yolo_class_catalog.py); el inventario completo por peso está en [`models/README.md`](../models/README.md).

| Familia de búsqueda (PoC) | Ejemplos de consulta | `clase_yolo` en índice |
|---------------------------|----------------------|------------------------|
| Piscinas | `piscinas`, `pool` | `swimming_pool`, `swimming pool` |
| Vehículos | `coches`, `camiones`, `vehicles` | `car`, `van`, `truck`, `bus`, `motor`, `small vehicle`, `large vehicle` |
| Edificios | `edificios`, `buildings` | `Building`, `building` |
| Paneles solares | `paneles solares`, `solar panels` | `photovoltaic panel` |
| Campos / pistas deportivas | `campos de fútbol`, `pista de baloncesto` | `soccer ball field`, `basketball court` |
| Peatones | `personas`, `peatones` | `pedestrian` |
| Rotondas | `rotonda`, `roundabout` | `roundabout` |

Esto **no** es un límite de arquitectura: es el vocabulario elegido para demostrar el flujo (detección → índice → consulta). Para ampliar el dominio:

1. Añadir o sustituir un peso en `CONFIGURED_MODELS` / `--model` y re-indexar (`detect` → `embed` → `embed2psql`).
2. Extender `YOLO_CLASS_CATALOG` (y, si aplica, atributos en `attribute_catalog.py`) con la nueva familia y sus sinónimos.
3. Documentar las clases del peso en [`models/README.md`](../models/README.md).

Clases emitidas por YOLO pero **fuera** de ese catálogo (p. ej. `plane`, `harbor`, `tennis court`) pueden existir en la tabla; la API no las resuelve por frase natural hasta que se añadan al catálogo.

### Ejecución batch

```powershell
cd D:\TFM\ares\tools
.\.venv\Scripts\Activate.ps1

python detect.py `
  --batch D:\TFM\data_madrid\tiles16 `
  --all-models `
  --skip-existing
```

Salidas:

- `…/16/x/y.json` por imagen
- `detection_summary.json` en la raíz del batch

Fragmento típico de detección:

```json
{
  "source_image": "D:\\TFM\\data_madrid\\tiles16\\16\\32101\\24711.png",
  "image_size": { "width": 2048, "height": 2048 },
  "detections": [
    {
      "class_id": 0,
      "class_name": "car",
      "confidence": 0.87,
      "source_model": "visdrone-yolov11s",
      "bbox": { "x1": 120.5, "y1": 340.0, "x2": 180.2, "y2": 390.1 },
      "bbox3857": { "x1": -412345.1, "y1": 4921000.2, "x2": -412300.0, "y2": 4921035.5 }
    }
  ]
}
```

### QA rápido

```powershell
python visualize.py D:\TFM\data_madrid\tiles16
```

Si no hay `bbox3857`, revisa que la ruta incluya `16/x/y` y que el PNG sea cuadrado.

---

## 6. Etiquetar / embeber con CLIP (`embed.py`)

CLIP no “etiqueta” clases nuevas: **embebe el recorte** de cada detección en un vector L2-normalizado de dimensión **512**, alineado con el encoder de texto de la API (`clip-ViT-B-32`). La búsqueda semántica compara el embedding de la consulta con estos vectores.

### Qué ocurre por tile

```python
# Esquema de tools/embed.py
detection_payload = load_detection_json(companion_json_path)
image_bgr = cv2.imread(str(source_image_path))

crops = []
for index, detection in enumerate(detection_payload["detections"]):
    crop = crop_detection_axis(image_bgr, detection, padding=padding)
    if crop is None:
        continue
    crops.append((index, detection, crop))

# CLIP image tower → tensor [N, 512], luego L2-normalize
vectors = encode_crops_with_clip(crops, model, processor, device, batch_size)

embeddings = [
    {
        "detection_index": detection_index,
        "class_name": detection["class_name"],
        "confidence": detection["confidence"],
        "source_model": detection["source_model"],
        "embedding": vector.tolist(),  # 512 floats
    }
    for ...
]
# Escrito en {stem}_emb.json
```

### Ejecución

```powershell
python embed.py `
  --batch D:\TFM\data_madrid\tiles16 `
  --skip-existing `
  --batch-size 16
```

Filtros útiles en pruebas:

```powershell
# Solo coches con conf ≥ 0.5
python embed.py --batch D:\TFM\data_madrid\tiles16 `
  --min-conf 0.5 --classes car --skip-existing
```

Salida: `24711_emb.json` con `embedding_dim: 512` y lista `embeddings` enlazada por `detection_index` al JSON YOLO (la geometría **no** se duplica aquí; `embed2psql` la lee del JSON de detecciones).

### Thumbnails (opcional)

Para previsualización ligera (no entran en el SQL de detecciones):

```powershell
python thumbnail.py --batch D:\TFM\data_madrid\tiles16 --skip-existing
# 24711.png → 24711_thumb.jpg (512×512 JPEG)
```

---

## 7. Exportar a la base de datos (`embed2psql.py` + psql)

Último paso offline: unir embeddings + geometrías EPSG:3857 y generar DDL/DML.

### Qué genera el script

| Fichero | Contenido |
|---------|-----------|
| `detecciones_catalogo_schema.sql` | Tabla catálogo + GIST en `bbox` |
| `{capa}_schema.sql` | Tabla de capa: `embedding vector(512)`, `geom`, índices GIST/HNSW |
| `detecciones_catalogo_data.sql` | `INSERT … ON CONFLICT` de la capa |
| `{capa}_data.sql` | `INSERT` por lotes (default 50 filas) |

Esquema de capa (resumen):

```sql
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS madrid_detections_example (
    id               SERIAL PRIMARY KEY,
    tile_id          VARCHAR NOT NULL,          -- '16/32101/24711'
    clase_yolo       VARCHAR NOT NULL,
    modelo_deteccion VARCHAR NOT NULL,
    embedding        vector(512) NOT NULL,
    geom             GEOMETRY(Polygon, 3857) NOT NULL,
    confianza        FLOAT NOT NULL,
    metadata         JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_madrid_detections_example_geom
    ON madrid_detections_example USING GIST (geom);

CREATE INDEX IF NOT EXISTS idx_madrid_detections_example_embedding
    ON madrid_detections_example USING hnsw (embedding vector_cosine_ops);
```

### Generar SQL

```powershell
cd D:\TFM\ares\tools

python embed2psql.py `
  --layer madrid_detections_example `
  --cog-path D:\TFM\data_madrid\cog\madrid_recortada_cog.tif `
  --batch D:\TFM\data_madrid\tiles16 `
  --output-dir D:\TFM\ares\sql_out `
  --strict
```

`--strict` falla si falta geometría 3857 (útil para no cargar filas sin geom).

Con URL pública (bbox desde tiles si no hay path):

```powershell
python embed2psql.py `
  --layer madrid_detections_example `
  --cog-url https://ejemplo.com/cogs/madrid_recortada_cog.tif `
  --batch D:\TFM\data_madrid\tiles16 `
  --output-dir D:\TFM\ares\sql_out
```

### Crear BD y cargar

```powershell
# Una vez: extensiones (también las crea el schema.sql)
psql -U postgres -c "CREATE DATABASE detecciones;"
psql -U postgres -d detecciones -c "CREATE EXTENSION IF NOT EXISTS postgis;"
psql -U postgres -d detecciones -c "CREATE EXTENSION IF NOT EXISTS vector;"

# Orden: catálogo schema → capa schema → capa data → catálogo data
psql -U postgres -d detecciones -f D:\TFM\ares\sql_out\detecciones_catalogo_schema.sql
psql -U postgres -d detecciones -f D:\TFM\ares\sql_out\madrid_detections_example_schema.sql
psql -U postgres -d detecciones -f D:\TFM\ares\sql_out\madrid_detections_example_data.sql
psql -U postgres -d detecciones -f D:\TFM\ares\sql_out\detecciones_catalogo_data.sql
```

### Verificación SQL

```sql
SELECT nombre_capa, total_detecciones, total_tiles, cog_url
FROM detecciones_catalogo;

SELECT clase_yolo, COUNT(*)
FROM madrid_detections_example
GROUP BY 1
ORDER BY 2 DESC
LIMIT 20;

SELECT tile_id, clase_yolo, confianza,
       ST_AsText(ST_Transform(ST_Centroid(geom), 4326)) AS centro_wgs84
FROM madrid_detections_example
LIMIT 5;
```

### Arrancar API sobre estos datos

En `api/.env`:

```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/detecciones
CATALOG_TABLE=detecciones_catalogo
```

```powershell
cd D:\TFM\ares\api
uvicorn main:app --reload --app-dir .
# GET /catalog debe listar madrid_detections_example
# POST /search {"query": "coches"} debe devolver features
```

---

## 8. Checklist de humo (dataset listo)

1. `gdalinfo` del COG OK (CRS + overviews).
2. URL del COG responde `206` a un `Range` (si está publicado).
3. Existe al menos un PNG `tiles16/16/x/y.png` y `build_tile_id` devuelve `16/x/y`.
4. El JSON YOLO tiene `bbox3857` en detecciones.
5. El `*_emb.json` tiene `embedding_dim: 512` y `embedding_count > 0`.
6. Tras `psql`, `/catalog` y una búsqueda por clase (`piscinas`, `coches`) devuelven GeoJSON.
7. (Espacial) Existen clases *target* y *reference* en la misma zona para probar `coches cerca de …`.

---

## 9. Problemas frecuentes

| Síntoma | Causa probable | Acción |
|---------|----------------|--------|
| Sin `bbox3857` | Ruta no es `z/x/y` o tile no cuadrado | Regenerar con `gdal2tiles --xyz` y tilesize cuadrado |
| `embed2psql` / `--strict` falla | Detecciones sin geom 3857 | Re-ejecutar `detect.py` sobre el layout correcto |
| Bbox del catálogo “desplazado” | Fallback mapml (malla XYZ) | Pasar `--cog-path` con geotags válidos |
| 0 filas en SQL | No hay `*_emb.json` o filtros `--classes`/`--min-conf` | Revisar `embedding_summary.json` |
| YOLO muy lento | Demasiados tiles / `--all-models` | AOI más pequeña; un solo `--model`; GPU CUDA si hay |
| CLIP OOM | `batch-size` alto en GPU | Bajar `--batch-size` (p. ej. 8) |
| API sin resultados | BD distinta / capa no en catálogo | Alinear `DATABASE_URL` y re-cargar `*_data.sql` |
| COG no streamea | Servidor sin Range | MinIO/S3/nginx; verificar con `curl -H Range` |

---

## 10. Script resumen (PowerShell)

Ajusta rutas y ejecuta por bloques (no lances YOLO/CLIP hasta validar tiles):

```powershell
$ROOT   = "D:\TFM\data_madrid"
$REPO   = "D:\TFM\ares"
$LAYER  = "madrid_detections_example"
$COG    = "$ROOT\cog\madrid_recortada_cog.tif"
$TILES  = "$ROOT\tiles16"
$SQLOUT = "$REPO\sql_out"

# 1–2) COG (si aún no existe)
gdal_translate -of COG -co COMPRESS=DEFLATE -co BLOCKSIZE=512 `
  "$ROOT\raw\ortofoto_aoi.tif" $COG

# 3) Publicar COG (ejemplo MinIO) — opcional
# mc cp $COG local/ares-cogs/

# 4) Tiles z=16
gdal2tiles.py --xyz --tilesize=2048 --zoom=16-16 --webviewer=none $COG $TILES

# 5–7) Pipeline Python
cd "$REPO\tools"
.\.venv\Scripts\Activate.ps1
python detect.py --batch $TILES --all-models --skip-existing
python embed.py --batch $TILES --skip-existing
python thumbnail.py --batch $TILES --skip-existing   # opcional
python embed2psql.py --layer $LAYER --cog-path $COG --batch $TILES --output-dir $SQLOUT --strict

# 8) Carga BD
psql -U postgres -d detecciones -f "$SQLOUT\detecciones_catalogo_schema.sql"
psql -U postgres -d detecciones -f "$SQLOUT\${LAYER}_schema.sql"
psql -U postgres -d detecciones -f "$SQLOUT\${LAYER}_data.sql"
psql -U postgres -d detecciones -f "$SQLOUT\detecciones_catalogo_data.sql"
```

---

## Referencias en el repositorio

- Pipeline CLI: [`tools/README.md`](../tools/README.md)
- Scripts: `detect.py`, `embed.py`, `thumbnail.py`, `embed2psql.py`, `utils.py`
- Consumo de los datos: [Guía de uso](guia-de-uso.md), [`api/README.md`](../api/README.md)
- Decisiones de diseño: [`.cursor/plans/`](../.cursor/plans/) (`script_embed2psql`, `script_clip_embeddings`, `scripts_yolo_urbanos`, …)
