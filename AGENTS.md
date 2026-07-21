# ARES — contexto para agentes

**ARES** (*AI Retrieval of Entities in Space*): búsqueda en lenguaje natural sobre detecciones en imágenes aéreas (YOLO + CLIP + PostGIS/pgvector + Ollama + FastAPI + OpenLayers).

Índice humano del repo: [`README.md`](README.md). Pipeline offline: [`tools/README.md`](tools/README.md). Preparación de datos: [`doc/preparacion-de-datos.md`](doc/preparacion-de-datos.md). API: [`api/README.md`](api/README.md).

## Stack

| Capa | Tecnología |
|------|------------|
| Detección / indexado | YOLO + CLIP en [`tools/`](tools/) |
| BD | PostgreSQL + PostGIS + pgvector |
| LLM local | Ollama (`llama3.2:3b` por defecto); se salta si la consulta es inequívoca |
| API | FastAPI en [`api/`](api/) (Clean Architecture) |
| Frontend (visor) | Next.js + OpenLayers en [`frontend/`](frontend/) |
| Visor de testing | [`api_webviewer/`](api_webviewer/) (secundario; pruebas de la API) |
| Memoria técnica | [`doc/memtech/`](doc/memtech/) |

## Layout del repo

```
ares/
├── README.md                 # índice del proyecto
├── AGENTS.md                 # este archivo
├── .cursor/plans/            # decisiones de diseño ya tomadas
├── api/                      # API de búsqueda semántica / espacial
│   ├── main.py, config.py, requirements.txt, .env.example
│   ├── api/                  # HTTP: routes, schemas, dependencies
│   ├── application/          # use cases + DTOs (search_detections)
│   ├── domain/               # entities, value objects, ports
│   ├── infrastructure/       # Postgres, CLIP, Ollama, parsers, GeoJSON
│   └── tests/
├── frontend/                 # visor de producto (Next.js + OpenLayers)
│   ├── app/, components/, lib/, hooks/
│   └── package.json, .env.example
├── api_webviewer/            # visor de testing de la API (mapa, tabla, JSON)
├── tools/                    # pipeline offline (detect → embed → SQL)
│   ├── detect.py, embed.py, embed2psql.py, thumbnail.py, visualize.py
│   └── utils.py
└── doc/                      # índice en doc/README.md; guías, capturas, memtech/
```

**No versionar:** `models/`, `data/`, `runs/`, `pruebas/`, `sql_test/`, `.venv/`, pesos `.pt`/`.onnx`, ni `.env`.

## Pipeline de búsqueda (API)

Orden en `SearchDetectionsUseCase` (no reordenar sin plan):

1. **Overrides HTTP** (`target`, o `target`+`reference`) → `interpretation.source=override`, sin Ollama.
2. **Parser determinista** (`try_deterministic_parse`) — match exacto de catálogo ± color ± espacial inequívoco → `source=parser`, sin Ollama.
3. **Ollama** + `apply_catalog_fallback` → `source=llm`.
4. CLIP embebe solo **target + atributos** (no la frase completa espacial).
5. `search_hybrid` (`search_class`) o `search_spatial_near` + `ST_DWithin` (`search_spatial` / relation `near`).
6. GeoJSON con `metadata.interpretation`, y en espacial `distance_to_reference_m` + `reference_features`.

Módulos clave:

| Área | Archivos |
|------|----------|
| Dominio | `domain/value_objects/semantic_query.py` (`StructuredQuery`, interpretación) |
| Spatial NL | `infrastructure/ai/spatial_query_parser.py` |
| Fast-path | `infrastructure/ai/deterministic_query_parser.py`, `find_catalog_entry_exact` |
| Catálogo / CLIP text | `yolo_class_catalog.py`, `attribute_catalog.py` |
| LLM | `infrastructure/ai/ollama_query_analyzer.py` |
| PostGIS | `postgres_detection_repository.py` (`search_hybrid`, `search_spatial_near`) |
| Respuesta | `infrastructure/geo/geojson_serializer.py` |

Ejemplos: `"piscinas"`, `"coches rojos"` → clase; `"coches cerca de rotonda"` → espacial. Overrides: `target`, `reference`, `spatial_relation=near`, `spatial_distance_m` (1–500).

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

Defaults (`api/config.py` / `.env.example`):

- DB: `postgresql+asyncpg://postgres:postgres@localhost:5432/detecciones`
- Ollama: `http://localhost:11434`, modelo `llama3.2:3b`
- CLIP: `clip-ViT-B-32`, dim 512
- Tabla catálogo: `detecciones_catalogo`
- Distancia espacial: `DEFAULT_SPATIAL_DISTANCE_M=50`, `MAX_SPATIAL_DISTANCE_M=500`

Tests: `pytest` desde `api/` (ver [`api/README.md`](api/README.md)).

### Frontend (visor)

```powershell
cd frontend
copy .env.example .env.local
npm install
npm run dev
```

URL API: `NEXT_PUBLIC_API_URL` en `.env.local`. UX de producto: mapa, tabla, interpretación, filtros, chips espaciales, distancia opcional, capa de referencias.

### Visor de testing (`api_webviewer`)

Secundario: servir estáticamente para probar la API a mano (mapa, tabla, JSON). URL en `api_webviewer/js/api.js`. Historial local opcional: `api_webviewer_search_history`.

### Pipeline offline

```powershell
cd tools
pip install -r requirements.txt
python detect.py --batch <tiles>/ --all-models
python embed.py --batch <tiles>/ --skip-existing
python thumbnail.py --batch <tiles>/ --skip-existing
python embed2psql.py --layer <capa> --cog-path <cog.tif> --batch <tiles>/
```

Pesos en `<repo>/models/` (fuera de git). Detalle en [`tools/README.md`](tools/README.md).

## Estado del producto (julio 2026)

**Hecho** (planes en `.cursor/plans/`):

- Scripts YOLO urbanos, CLIP embeddings, thumbnails 512, carga a PostgreSQL
- API de búsqueda semántica híbrida (clase YOLO + ranking CLIP)
- Visor web de producto ([`frontend/`](frontend/)); `api_webviewer` queda como testing de la API
- Analizador de consultas vía Ollama local
- **Consulta espacial enriquecida** (`target` / `reference` / `relation=near`, `ST_DWithin`, CLIP solo target+attrs, interpretación en API + frontend) — plan `consulta_espacial_enriquecida_abdaa577`
- **Fast-path sin LLM** (overrides + parser determinista; `llm_ms=0`) — plan `fast-path_sin_llm_484fbd49`
- **Historial de búsquedas** en `api_webviewer` (últimas 5, solo texto, localStorage) — plan `historial_búsquedas_viewer_172cb185`

**Fuera de alcance / siguiente (si se retoma):**

- Relación `inside` / `within` (schema preparado, sin implementar)
- Filtro `bbox` / fase espacial adicional
- LRU / caché de interpretaciones Ollama

## Convenciones para el agente

1. Leer `.cursor/plans/` antes de reimplementar decisiones ya tomadas.
2. Memoria narrativa en `doc/memtech/`; no contradecir el resumen sin actualizar docs.
3. No meter datasets, pesos ni `.env` en commits.
4. Pipeline offline vive en `tools/`; la API en `api/` — no mezclar responsabilidades.
5. Cambios de API: mantener tests en `api/tests/` y compatibilidad del GeoJSON cuando sea posible (`metadata.interpretation`, campos espaciales).
6. Cambios mínimos y enfocados; no refactorizar fuera del alcance pedido.
7. No llamar Ollama si overrides o el parser determinista ya resuelven la consulta; preservar el orden override → parser → LLM.

## Origen

Importado desde `D:\TFM\yolo_example`. Los chats de Cursor de esa carpeta no se migran; este archivo + `.cursor/plans/` + `README.md` son el contexto portable.
