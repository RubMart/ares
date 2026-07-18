# API de búsqueda semántica (ARES)

FastAPI que interpreta consultas en lenguaje natural (ES/EN), genera embeddings CLIP de texto y busca detecciones en PostgreSQL + PostGIS + pgvector. Respuesta en GeoJSON.

Índice del monorepo: [`../README.md`](../README.md).

## Requisitos

| Componente | Uso |
|------------|-----|
| Python 3.11+ (recomendado) | Runtime de la API |
| PostgreSQL + PostGIS + pgvector | Catálogo de capas y detecciones con embeddings |
| [Ollama](https://ollama.com/) | Análisis semántico de la consulta (`llama3.2:3b` por defecto) |
| Red (opcional) | Solo si CLIP no está en caché local ni en `models/` |

Dependencias Python: [`requirements.txt`](requirements.txt) (FastAPI, SQLAlchemy/asyncpg, transformers/torch, langchain-ollama, etc.).

## Estructura

```
api/
├── main.py                 # App FastAPI + CORS + lifespan
├── config.py               # Settings (pydantic-settings + .env)
├── requirements.txt
├── .env.example
├── pytest.ini
├── api/                    # Capa HTTP
│   ├── routes/             # /health, /catalog, /search
│   ├── schemas/
│   └── dependencies.py
├── application/            # Casos de uso y DTOs
├── domain/                 # Entidades, value objects, puertos
├── infrastructure/         # Postgres, CLIP, Ollama, GeoJSON
└── tests/
```

Clean Architecture: HTTP → use cases → repositorios / servicios (CLIP, LLM).

## Instalación

Desde la carpeta `api/`. Copia primero la configuración:

```powershell
copy .env.example .env
```

Ajusta `DATABASE_URL`, Ollama y CLIP en `.env` (no se versiona).

### Con venv

```powershell
cd api
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Linux/macOS:

```bash
cd api
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Con Conda

```powershell
cd api
conda create -n ares-api python=3.11 -y
conda activate ares-api
pip install -r requirements.txt
```

(Opcional) Si prefieres PyTorch por canal Conda, instálalo antes y luego el resto con `pip install -r requirements.txt`.

### Servicios externos

1. PostgreSQL accesible con la URL de `DATABASE_URL` (driver `postgresql+asyncpg://...`).
2. Ollama en marcha y modelo tirado, p. ej.:

```powershell
ollama pull llama3.2:3b
ollama serve
```

## Ejecución

Con el entorno activado y el cwd en `api/`:

```powershell
uvicorn main:app --reload --app-dir .
```

- API: `http://127.0.0.1:8000`
- OpenAPI: `http://127.0.0.1:8000/docs`

Arranque en frío: carga CLIP en el lifespan (puede tardar la primera vez).

## Endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/health` | Estado de BD, Ollama y metadatos CLIP |
| `GET` | `/catalog` | Capas del catálogo (`detecciones_catalogo` por defecto) |
| `POST` | `/search` | Búsqueda híbrida → FeatureCollection GeoJSON |

### `POST /search`

Cuerpo JSON:

```json
{
  "query": "coches rojos",
  "top_k": 50,
  "per_layer_limit": 100,
  "min_confidence": 0.0
}
```

Solo `query` es obligatorio. El resto usa defaults de `.env` / `config.py`.

Flujo: Ollama estructura la consulta → CLIP embebe el texto → filtro por clase YOLO + ranking por similitud coseno en pgvector → GeoJSON.

Errores frecuentes: `400` validación, `503` LLM no disponible, `500` error interno.

## Gestión de modelos

La API **no** ejecuta YOLO. Solo necesita:

1. **Ollama** — modelo LLM local (`OLLAMA_MODEL`, p. ej. `llama3.2:3b`).
2. **CLIP texto** — mismo espacio que `tools/embed.py` (`openai/clip-vit-base-patch32`, 512-d). Alias: `clip-ViT-B-32`.

### Resolución de CLIP (`CLIP_MODEL_NAME` + `CLIP_LOCAL_DIR`)

Orden al arrancar:

1. Si `CLIP_MODEL_NAME` es una carpeta local válida (`config.json`) → se usa esa ruta.
2. Si el alias canónico apunta a `CLIP_LOCAL_DIR` (por defecto `../models/clip-vit-base-patch32`) y existe → se usa el proyecto.
3. Si hay snapshot en la **caché de Hugging Face** (`~/.cache/huggingface/hub/models--openai--clip-vit-base-patch32/...`) → se usa esa caché (puede no aparecer nada en `models/`).
4. Si no → descarga pública a `CLIP_LOCAL_DIR` (`snapshot_download` con `token=False` para no fallar por un token HF inválido).

Variables relevantes en `.env`:

```env
CLIP_MODEL_NAME=clip-ViT-B-32
CLIP_LOCAL_DIR=../models/clip-vit-base-patch32
CLIP_ONNX_BACKEND=false
EMBEDDING_DIM=512
```

`models/` está en `.gitignore`. Los pesos YOLO del pipeline offline viven aparte (`../models/*.pt`) y **no** los usa esta API.

Si Hugging Face falla con *Repository Not Found* / *OAuth token signature verification failed*, suele ser un token local corrupto: `hf auth logout` o borrar `~/.cache/huggingface/token`. Con la caché HF ya poblada, la API arranca sin red.

## Tests

Instalar herramientas de test (no van en `requirements.txt`):

```powershell
pip install pytest pytest-asyncio httpx
```

Desde `api/` con el entorno activado:

```powershell
# Toda la suite (unitarios + rutas mockeadas)
pytest

# Solo núcleo / resolución CLIP / catálogo
pytest tests/test_core.py -q

# Casos de uso y rutas
pytest tests/test_search_use_case.py tests/test_api_routes.py -q
```

Integración con BD real (opcional; omitida por defecto):

```powershell
$env:RUN_DB_INTEGRATION="1"
pytest tests/test_integration_db.py -q
```

Requiere `DATABASE_URL` válida y datos de catálogo cargados.

## Configuración rápida

| Variable | Default | Notas |
|----------|---------|--------|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/detecciones` | Obligatoria en práctica |
| `CATALOG_TABLE` | `detecciones_catalogo` | |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | |
| `OLLAMA_MODEL` | `llama3.2:3b` | |
| `CLIP_MODEL_NAME` | `clip-ViT-B-32` | Alias o ruta local |
| `CLIP_LOCAL_DIR` | `../models/clip-vit-base-patch32` | Relativo a `api/` |
| `DEFAULT_TOP_K` | `50` | |
| `CORS_ORIGINS` | `["*"]` | JSON en `.env` |
