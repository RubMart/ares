# tools — pipeline de detección e indexación

Scripts CLI para pasar de ortofoto/tile a filas en PostgreSQL (PostGIS + pgvector).

Guía técnica completa (COG, publicación HTTP, `gdal2tiles` z=16, YOLO, CLIP, SQL): [`doc/preparacion-de-datos.md`](../doc/preparacion-de-datos.md).

## Flujo

```
thumbnail.py  (opcional)
     ↓
detect.py     →  {stem}.json          detecciones YOLO
     ↓
embed.py      →  {stem}_emb.json      embeddings CLIP (512-d, L2)
     ↓
embed2psql.py →  *_schema.sql / *_data.sql
     ↓
psql -f …     →  tablas + catálogo
```

`visualize.py` abre una GUI PyQt6 para revisar detecciones (no forma parte del indexado).

## Dependencias

```powershell
cd tools
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Pesos YOLO se descargan/cachean en `<repo>/models/` (gitignored).

## Scripts

| Script | Rol |
|--------|-----|
| `detect.py` | Inferencia YOLO (uno o `--all-models`) → JSON junto a la imagen |
| `embed.py` | Recorte por bbox + CLIP imagen → `*_emb.json` |
| `thumbnail.py` | JPEG 512×512 (`*_thumb.jpg`) para transmisión rápida |
| `embed2psql.py` | Genera SQL schema/data + catálogo de capas (COG) |
| `visualize.py` | Visor local de detecciones |
| `utils.py` | Rutas companion, tiles gdal2tiles, geometría EPSG:3857 |

## Ejemplos

Desde esta carpeta (`tools/`):

```powershell
python detect.py --batch D:/TFM/.../tiles16/ --all-models --skip-existing
python embed.py --batch D:/TFM/.../tiles16/ --skip-existing
python thumbnail.py --batch D:/TFM/.../tiles16/ --skip-existing
python embed2psql.py --layer madrid_detections_example `
  --cog-path D:/TFM/cog_madrid/madrid_recortada_cog.tif `
  --batch D:/TFM/.../tiles16/
```

Desde la raíz del repo:

```powershell
python tools/detect.py --help
```

(`utils` se resuelve porque Python añade el directorio del script a `sys.path`.)

## Salidas por defecto

- Pesos: `<repo>/models/`
- SQL de `embed2psql.py`: raíz del repo (override con `--output-dir`)
