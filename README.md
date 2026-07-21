# ARES

**AI Retrieval of Entities in Space**

ARES es un sistema de búsqueda en lenguaje natural sobre **detecciones de objetos en imágenes aéreas**. Permite preguntar, en español o en inglés, cosas como «piscinas», «coches rojos» o «coches cerca de rotonda», y obtener las entidades georreferenciadas correspondientes sobre un mapa, sin construir filtros GIS a mano.

El flujo de producto es:

1. Las imágenes aéreas se procesan offline (YOLO + CLIP) y se indexan en PostgreSQL con PostGIS y pgvector.
2. La API interpreta la consulta (parser determinista u Ollama), embebe el texto con CLIP y busca en la base de datos (filtro por clase, ranking semántico y, si aplica, proximidad espacial con `ST_DWithin`).
3. El visor web muestra resultados en mapa, tabla y JSON, con la interpretación de la consulta visible para el usuario.

![Interfaz de ARES: mapa con detecciones y filtros](doc/.images/ares_map_interface.png)

## Qué problema resuelve

Las ortofotos de alta resolución contienen mucha información territorial (vehículos, edificios, infraestructuras, etc.), pero el acceso suele pasar por herramientas GIS, catálogos rígidos o SQL. ARES reduce esa barrera: convierte detecciones ya indexadas en un índice **semántico y espacial** consultable con frases naturales, y entrega un GeoJSON listo para visualización.

## Stack

| Capa | Tecnología |
|------|------------|
| Detección / indexado (offline) | YOLO + CLIP en [`tools/`](tools/) |
| Base de datos | PostgreSQL + PostGIS + pgvector |
| Interpretación de consultas | Parser determinista + Ollama (`llama3.2:3b` por defecto) |
| API | FastAPI ([`api/`](api/)) |
| Visor | OpenLayers ([`api_webviewer/`](api_webviewer/)) |

## Estructura del repositorio

| Ruta | Contenido |
|------|-----------|
| [`api/`](api/) | API REST de búsqueda semántica / espacial |
| [`api_webviewer/`](api_webviewer/) | Visor: mapa, tabla, JSON e historial local |
| [`tools/`](tools/) | Pipeline offline: detección, embeddings, thumbnails, SQL |
| [`doc/`](doc/) | Guía de uso, capturas y memoria técnica |
| [`AGENTS.md`](AGENTS.md) | Contexto operativo para agentes / desarrollo |
| [`.cursor/plans/`](.cursor/plans/) | Decisiones de diseño ya tomadas |

Datos, pesos YOLO/CLIP y entornos virtuales **no** van en el repo (`models/`, `data/`, `.venv/`, …). Ver [`.gitignore`](.gitignore).

El pipeline de indexación (detect → embed → PostgreSQL) se documenta en [`tools/README.md`](tools/README.md).

## Arranque rápido

Antes de arrancar API o visor hace falta una **base de datos PostgreSQL** con PostGIS y pgvector, con el catálogo de capas y las tablas de detecciones ya cargadas (por defecto BD `detecciones`). Sin ese índice no hay resultados que consultar. La carga de datos se hace con el pipeline de [`tools/`](tools/).

También se recomienda tener **Ollama** en marcha (`ollama pull llama3.2:3b`) para consultas ambiguas; las inequívocas pueden resolverse sin LLM.

### API

```powershell
cd api
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
uvicorn main:app --reload --app-dir .
```

Ajusta `DATABASE_URL` en `.env` si tu PostgreSQL no usa los defaults (`postgresql+asyncpg://postgres:postgres@localhost:5432/detecciones`).

- API: `http://127.0.0.1:8000`
- OpenAPI interactivo: `http://127.0.0.1:8000/docs`

Detalle de instalación, endpoints y configuración: [`api/README.md`](api/README.md).

### Frontend (visor)

Con la API en marcha, sirve estáticamente [`api_webviewer/`](api_webviewer/):

```powershell
cd api_webviewer
python -m http.server 8080
```

Abre `http://localhost:8080`. La URL base de la API se configura en el propio visor (por defecto `http://localhost:8000`; también en `api_webviewer/js/api.js`).

## Guía

| Documento | Contenido |
|-----------|-----------|
| [Guía de uso](doc/guia-de-uso.md) | Cómo buscar desde el visor, tipos de consulta, mapa, filtros e interpretación |
| [API reference](api/README.md) | Endpoints, cuerpo de `POST /search`, configuración y tests |
| [OpenAPI](http://127.0.0.1:8000/docs) | Documentación interactiva (con la API en marcha) |
| [Pipeline offline](tools/README.md) | Detección YOLO, embeddings CLIP y carga a PostgreSQL |
| [Memoria técnica](doc/memtech/) | Narrativa del TFM |
