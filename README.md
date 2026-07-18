# ARES

**AI Retrieval of Entities in Space**

Búsqueda en lenguaje natural sobre detecciones en imágenes aéreas: YOLO → CLIP → PostGIS/pgvector → Ollama → API → mapa.

## Estructura

| Ruta | Contenido |
|------|-----------|
| [`api/`](api/) | API REST FastAPI (búsqueda semántica / espacial) |
| [`api_webviewer/`](api_webviewer/) | Visor OpenLayers (mapa, tabla, JSON) |
| [`tools/`](tools/) | Pipeline offline: detección, embeddings, thumbnails, SQL |
| [`doc/memtech/`](doc/memtech/) | Memoria técnica del TFM |
| [`AGENTS.md`](AGENTS.md) | Contexto operativo para agentes / desarrollo |
| [`.cursor/plans/`](.cursor/plans/) | Decisiones de diseño ya tomadas |

Datos, pesos YOLO/CLIP y entornos virtuales **no** van en el repo (`models/`, `data/`, `.venv/`, …). Ver [`.gitignore`](.gitignore).

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

Defaults: PostgreSQL `detecciones`, Ollama `llama3.2:3b`, CLIP `clip-ViT-B-32` (dim 512). Guía completa: [`api/README.md`](api/README.md). Contexto agentes: [`AGENTS.md`](AGENTS.md).

### Visor

Servir estáticamente [`api_webviewer/`](api_webviewer/) (la URL de la API está en `api_webviewer/js/api.js`).

### Pipeline offline

```powershell
cd tools
pip install -r requirements.txt
python detect.py --batch <tiles>/ --all-models
python embed.py --batch <tiles>/ --skip-existing
python thumbnail.py --batch <tiles>/ --skip-existing
python embed2psql.py --layer <capa> --cog-path <cog.tif> --batch <tiles>/
```

Guía del pipeline: [`tools/README.md`](tools/README.md).

## Estado

- **Listo:** detección YOLO, embeddings CLIP, carga PostGIS, API híbrida, visor, LLM vía Ollama.
- **Siguiente:** consulta espacial enriquecida (target / reference / relation + `ST_DWithin`). Plan: `.cursor/plans/consulta_espacial_enriquecida_abdaa577.plan.md`.
