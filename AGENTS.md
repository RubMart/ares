# ARES — contexto para agentes

**ARES** (*AI Retrieval of Entities in Space*): búsqueda en lenguaje natural sobre detecciones en imágenes aéreas (YOLO + CLIP + PostGIS/pgvector + Ollama + FastAPI + OpenLayers).

Índice humano del repo: [`README.md`](README.md). Pipeline offline: [`tools/README.md`](tools/README.md).

## Stack

| Capa | Tecnología |
|------|------------|
| Detección / indexado | YOLO + CLIP en [`tools/`](tools/) |
| BD | PostgreSQL + PostGIS + pgvector |
| LLM local | Ollama (`llama3.2:3b` por defecto) |
| API | FastAPI en [`api/`](api/) |
| Visor | OpenLayers en [`api_webviewer/`](api_webviewer/) |
| Memoria técnica | [`doc/memtech/`](doc/memtech/) |

## Layout del repo

```
ares/
├── README.md                 # índice del proyecto
├── AGENTS.md                 # este archivo
├── .cursor/plans/            # decisiones de diseño ya tomadas
├── api/                      # API de búsqueda semántica
│   ├── main.py
│   ├── config.py
│   ├── requirements.txt
│   ├── .env.example
│   ├── domain/ application/ infrastructure/ api/
│   └── tests/
├── api_webviewer/            # cliente mapa + tabla + JSON
├── tools/                    # pipeline offline (detect → embed → SQL)
│   ├── requirements.txt
│   ├── detect.py, embed.py, embed2psql.py, thumbnail.py, visualize.py
│   └── utils.py
└── doc/memtech/              # memoria técnica del TFM
```

**No versionar:** `models/`, `data/`, `runs/`, `pruebas/`, `sql_test/`, `.venv/`, pesos `.pt`/`.onnx`, ni `.env`.

## Arranque rápido

### API

```powershell
cd api
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
uvicorn main:app --reload --app-dir .
```

Defaults (`api/config.py`):

- DB: `postgresql+asyncpg://postgres:postgres@localhost:5432/detecciones`
- Ollama: `http://localhost:11434`, modelo `llama3.2:3b`
- CLIP: `clip-ViT-B-32`, dim 512
- Tabla catálogo: `detecciones_catalogo`

### Visor

Servir `api_webviewer/` con un HTTP estático (URL API en `api_webviewer/js/api.js`).

### Pipeline offline

```powershell
cd tools
pip install -r requirements.txt
python detect.py --batch <tiles>/ --all-models
python embed.py --batch <tiles>/ --skip-existing
python embed2psql.py --layer <capa> --cog-path <cog.tif> --batch <tiles>/
```

Pesos en `<repo>/models/` (fuera de git). Detalle en [`tools/README.md`](tools/README.md).

## Estado del producto (julio 2026)

**Hecho** (planes en `.cursor/plans/`):

- Scripts YOLO urbanos, CLIP embeddings, thumbnails 512, carga a PostgreSQL
- API de búsqueda semántica híbrida (clase YOLO + ranking CLIP)
- Visor web OpenLayers
- Analizador de consultas vía Ollama local

**En curso / siguiente:** consulta espacial enriquecida  
Plan: `.cursor/plans/consulta_espacial_enriquecida_abdaa577.plan.md`

Objetivo: *target* / *reference* / *relation* (p. ej. «coches cerca de una rotonda»), proximidad con PostGIS (`ST_DWithin`), CLIP solo sobre target+attrs, interpretación visible en API + viewer.

## Convenciones para el agente

1. Leer `.cursor/plans/` antes de reimplementar decisiones ya tomadas.
2. Memoria narrativa en `doc/memtech/`; no contradecir el resumen sin actualizar docs.
3. No meter datasets, pesos ni `.env` en commits.
4. Pipeline offline vive en `tools/`; la API en `api/` — no mezclar responsabilidades.
5. Cambios de API: mantener tests en `api/tests/` y compatibilidad del GeoJSON cuando sea posible.
6. Cambios mínimos y enfocados; no refactorizar fuera del alcance pedido.

## Origen

Importado desde `D:\TFM\yolo_example`. Los chats de Cursor de esa carpeta no se migran; este archivo + `.cursor/plans/` + `README.md` son el contexto portable.
