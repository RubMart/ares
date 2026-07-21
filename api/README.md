# API de búsqueda semántica (ARES)

FastAPI que interpreta consultas en lenguaje natural (ES/EN), genera embeddings CLIP de texto y busca detecciones en PostgreSQL + PostGIS + pgvector. Respuesta en GeoJSON.

Capacidades actuales:

- **Fast-path sin LLM** — overrides HTTP y parser determinista; Ollama solo si la frase es ambigua
- **Búsqueda híbrida** — filtro por clase YOLO + ranking CLIP (`pgvector`)
- **Consulta espacial** — `near` con `ST_DWithin` (target / reference / distancia)
- **Caché LRU** de interpretaciones LLM (`GET`/`DELETE /cache/llm`)
- **Rate limit** en `POST /search` (slowapi)

Índice del monorepo: [`../README.md`](../README.md).

## Requisitos

| Componente | Uso |
|------------|-----|
| Python 3.11+ (recomendado) | Runtime de la API |
| PostgreSQL + PostGIS + pgvector | Catálogo de capas y detecciones con embeddings |
| [Ollama](https://ollama.com/) | Análisis semántico de consultas ambiguas (`llama3.2:3b` por defecto) |
| Red (opcional) | Solo si CLIP no está en caché local ni en `models/` |

### Dependencias Python (`requirements.txt`)

| Grupo | Paquetes |
|-------|----------|
| Web API | `fastapi`, `uvicorn[standard]`, `slowapi` |
| Config / validación | `pydantic`, `pydantic-settings`, `python-dotenv` |
| BD | `sqlmodel`, `sqlalchemy[asyncio]`, `asyncpg`, `greenlet`, `pgvector`, `geoalchemy2` |
| LLM (Ollama) | `langchain-ollama`, `langchain-core` |
| CLIP texto | `transformers`, `huggingface-hub`, `Pillow`, `torch`, `optimum[onnxruntime]`, `onnxruntime` |
| HTTP util | `httpx` (p. ej. health de Ollama) |

Instalar siempre desde `requirements.txt` (ver [Instalación](#instalación)). Herramientas de test (`pytest`, `pytest-asyncio`) no van en ese fichero; ver [Tests](#tests). `httpx` sí está en runtime porque la API lo usa fuera de los tests.

## Estructura

```
api/
├── main.py                 # App FastAPI + CORS + lifespan + rate limit
├── config.py               # Settings (pydantic-settings + .env)
├── requirements.txt
├── .env.example
├── pytest.ini
├── api/                    # Capa HTTP
│   ├── routes/             # /health, /catalog, /search, /cache/llm
│   ├── schemas/
│   ├── rate_limit.py       # Limiter slowapi
│   └── dependencies.py     # Composition root (CLIP + CachingQueryAnalyzer)
├── application/            # Casos de uso y DTOs
├── domain/                 # Entidades, value objects, puertos
├── infrastructure/         # Postgres, CLIP, Ollama, parsers, GeoJSON, caché LRU
└── tests/
```

Clean Architecture: HTTP → use cases → repositorios / servicios (CLIP, LLM).

## Instalación

Trabaja siempre desde la carpeta `api/`. Copia primero la configuración:

```powershell
cd api
copy .env.example .env
```

Linux/macOS: `cp .env.example .env`.

Ajusta al menos `DATABASE_URL` (y, si hace falta, Ollama y CLIP) en `.env`. Ese fichero **no** se versiona.

### Con venv

**Windows (PowerShell):**

```powershell
cd api
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

**Linux / macOS:**

```bash
cd api
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Para salir del entorno: `deactivate`.

Si la política de ejecución de PowerShell bloquea `Activate.ps1`:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

### Con Conda

Útil si ya usas Anaconda/Miniconda o quieres fijar Python sin tocar el sistema:

```powershell
cd api
conda create -n ares-api python=3.11 -y
conda activate ares-api
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Notas:

- Tras `conda activate ares-api`, las dependencias de la API se instalan con **pip** sobre ese entorno (mismo `requirements.txt` que con venv).
- (Opcional) PyTorch por canal Conda antes del resto, p. ej. `conda install pytorch cpuonly -c pytorch`, y después `pip install -r requirements.txt`. Si `pip` reinstala `torch`, prioriza la versión que necesites (CPU/CUDA).
- Salir del entorno: `conda deactivate`.
- El `.venv` de pip y el env de Conda son alternativas; no hace falta activar ambos.

### Servicios externos

1. **PostgreSQL** accesible con la URL de `DATABASE_URL` (driver `postgresql+asyncpg://...`), con PostGIS, pgvector y datos de catálogo/detecciones cargados (ver [`../tools/README.md`](../tools/README.md)).
2. **Ollama** en marcha y modelo tirado (solo necesario para consultas ambiguas; el fast-path no lo llama):

```powershell
ollama pull llama3.2:3b
ollama serve
```

## Ejecución

Con el entorno activado (venv o conda) y el cwd en `api/`:

```powershell
uvicorn main:app --reload --app-dir .
```

- API: `http://127.0.0.1:8000`
- OpenAPI: `http://127.0.0.1:8000/docs`

Arranque en frío: carga CLIP en el lifespan (puede tardar la primera vez).

## Endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/health` | Estado de BD, Ollama y metadatos CLIP (`ok` / `degraded`) |
| `GET` | `/catalog` | Capas del catálogo (`detecciones_catalogo` por defecto) |
| `POST` | `/search` | Búsqueda híbrida / espacial → FeatureCollection GeoJSON (rate-limited) |
| `GET` | `/cache/llm` | Metadatos y claves de la caché LRU de interpretaciones |
| `DELETE` | `/cache/llm` | Vacía toda la caché LRU de interpretaciones |

### `POST /search`

Cuerpo JSON (consulta simple):

```json
{
  "query": "coches rojos",
  "top_k": 50,
  "per_layer_limit": 100,
  "min_confidence": 0.0
}
```

Consulta espacial (NL o con overrides explícitos):

```json
{
  "query": "coches cerca de rotonda",
  "target": "vehicle",
  "reference": "roundabout",
  "spatial_relation": "near",
  "spatial_distance_m": 30
}
```

Solo `query` es obligatorio (1–`MAX_QUERY_LENGTH` caracteres; default 500). Campos opcionales:

| Campo | Efecto |
|-------|--------|
| `top_k`, `per_layer_limit`, `min_confidence` | Límites de ranking / filtrado (defaults en settings) |
| `target`, `reference` | Overrides de objeto buscado y de referencia espacial |
| `spatial_relation` | Solo `near` en v1 |
| `spatial_distance_m` | Radio en metros (1–`MAX_SPATIAL_DISTANCE_M`; default efectivo `DEFAULT_SPATIAL_DISTANCE_M`) |

Los overrides tienen prioridad sobre la interpretación automática.

Flujo de interpretación (salta Ollama cuando no hace falta):

1. Overrides suficientes (`target`, o `target`+`reference`) → `interpretation.source=override`, sin LLM.
2. Match determinista inequívoco (catálogo exacto ± color ± espacial, p. ej. `"piscinas"`, `"coches rojos"`, `"coches cerca de rotonda"`) → `source=parser`, sin LLM.
3. Si no → caché LRU del analizador (`source=cache` en hit) o Ollama + fallback de catálogo (`source=llm`). Ver [Caché LRU de interpretaciones](#caché-lru-de-interpretaciones).

Después: CLIP embebe solo el *target* (+ atributos) → `search_hybrid` (clase) o `search_spatial_near` (`ST_DWithin`) → GeoJSON con `metadata.interpretation` (y `distance_to_reference_m` / `reference_features` en espacial).

**Índices espaciales recomendados** por capa (EPSG:3857, unidades ~metros):

```sql
CREATE INDEX IF NOT EXISTS idx_<capa>_geom ON <capa> USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_<capa>_clase_geom ON <capa> (clase_yolo) INCLUDE (geom);
```

Errores frecuentes:

| Código | Causa típica |
|--------|----------------|
| `400` | Validación (p. ej. referencia espacial ausente o no mapeable) |
| `429` | Rate limit de `POST /search` superado |
| `503` | LLM no disponible cuando la consulta requiere Ollama |
| `500` | Error interno |

## Caché LRU de interpretaciones

Cuando la consulta llega al analizador LLM, `CachingQueryAnalyzer` envuelve `OllamaQueryAnalyzer` y guarda en memoria el `StructuredQuery` resultante para no repetir la llamada a Ollama con el mismo texto.

| Aspecto | Comportamiento |
|---------|----------------|
| Ámbito | Solo el paso 3 del pipeline (tras overrides y parser). No cachea CLIP ni SQL. |
| Clave | `{OLLAMA_MODEL}\|{query_normalizada}` — NFKC, trim, colapso de espacios, `casefold` |
| Política | LRU en proceso (`OrderedDict`); tamaño `LLM_CACHE_MAXSIZE` (default `256`) |
| Desactivar | `LLM_CACHE_MAXSIZE=0` |
| Persistencia | Volátil: se pierde al reiniciar uvicorn |
| Respuesta | Hit → `metadata.interpretation.source=cache`; miss → `source=llm` |
| `llm_ms` | En hit ≈ lookup en memoria; en miss, el tiempo de Ollama |

Inspección y vaciado (útil en lab / demos):

```powershell
# Estado: size, maxsize, enabled, keys
curl http://127.0.0.1:8000/cache/llm

# Vaciar
curl -X DELETE http://127.0.0.1:8000/cache/llm
```

Si el analizador inyectado no es `CachingQueryAnalyzer` (p. ej. tests con mock), ambos endpoints responden `404` con `"LLM cache not available"`.

La caché **no** sustituye el fast-path: overrides y parser determinista siguen evitando Ollama en la primera petición. La LRU solo acelera paráfrasis / consultas ambiguas que ya pasaron por el modelo. Implementación: `infrastructure/ai/caching_query_analyzer.py`; tests: `tests/test_caching_query_analyzer.py`, rutas en `tests/test_api_routes.py`.

## Gestión de modelos

La API **no** ejecuta YOLO. Solo necesita:

1. **Ollama** — modelo LLM local (`OLLAMA_MODEL`, p. ej. `llama3.2:3b`).
2. **CLIP texto** — mismo espacio que `tools/embed.py` (`openai/clip-vit-base-patch32`, 512-d). Alias: `clip-ViT-B-32`. Backend PyTorch por defecto; ONNX opcional (`CLIP_ONNX_BACKEND=true`).

### Resolución de CLIP (`CLIP_MODEL_NAME` + `CLIP_LOCAL_DIR`)

Orden al arrancar:

1. Si `CLIP_MODEL_NAME` es una carpeta local válida (`config.json`) → se usa esa ruta.
2. Si el alias canónico apunta a `CLIP_LOCAL_DIR` (por defecto `../models/clip-vit-base-patch32`) y existe → se usa el proyecto.
3. Si hay snapshot en la **caché de Hugging Face** (`~/.cache/huggingface/hub/models--openai--clip-vit-base-patch32/...`) → se usa esa caché (puede no aparecer nada en `models/`).
4. Si no → descarga pública a `CLIP_LOCAL_DIR` (`snapshot_download` con `token=False` para no fallar por un token HF inválido).

`models/` está en `.gitignore`. Los pesos YOLO del pipeline offline viven aparte (`../models/*.pt`) y **no** los usa esta API.

Si Hugging Face falla con *Repository Not Found* / *OAuth token signature verification failed*, suele ser un token local corrupto: `hf auth logout` o borrar `~/.cache/huggingface/token`. Con la caché HF ya poblada, la API arranca sin red.

## Tests

Instalar herramientas de test (no van en `requirements.txt`):

```powershell
pip install pytest pytest-asyncio
```

(`httpx` ya está en `requirements.txt`; hace falta para el cliente de pruebas de FastAPI.)

Desde `api/` con el entorno activado:

```powershell
# Toda la suite (unitarios + rutas mockeadas)
pytest

# Núcleo / resolución CLIP / catálogo
pytest tests/test_core.py -q

# Casos de uso, parsers, caché y rutas
pytest tests/test_search_use_case.py tests/test_deterministic_query_parser.py tests/test_caching_query_analyzer.py tests/test_api_routes.py -q
```

Integración con BD real (opcional; omitida por defecto):

```powershell
$env:RUN_DB_INTEGRATION="1"
pytest tests/test_integration_db.py -q
```

Requiere `DATABASE_URL` válida y datos de catálogo cargados.

## Variables de entorno

Plantilla: [`.env.example`](.env.example). Copia a `.env` y ajusta. Los defaults coinciden con `config.py` si no hay `.env`.

### App / HTTP

| Variable | Default | Notas |
|----------|---------|--------|
| `DEBUG` | `false` | Modo debug de FastAPI |
| `CORS_ORIGINS` | `["*"]` | Lista JSON en `.env` |
| `RATE_LIMIT_ENABLED` | `true` | Rate limit de `POST /search` |
| `RATE_LIMIT_SEARCH` | `30/minute` | Formato slowapi (`N/minute`, `N/hour`, …) |

### Base de datos

| Variable | Default | Notas |
|----------|---------|--------|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/detecciones` | Obligatoria en práctica |
| `CATALOG_TABLE` | `detecciones_catalogo` | Tabla de capas |

### Ollama / caché LLM

| Variable | Default | Notas |
|----------|---------|--------|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | |
| `OLLAMA_MODEL` | `llama3.2:3b` | |
| `OLLAMA_TEMPERATURE` | `0.0` | |
| `LLM_CACHE_MAXSIZE` | `256` | LRU en memoria; `0` = off. Detalle: [Caché LRU](#caché-lru-de-interpretaciones) (`GET`/`DELETE` `/cache/llm`) |

### CLIP

| Variable | Default | Notas |
|----------|---------|--------|
| `CLIP_MODEL_NAME` | `clip-ViT-B-32` | Alias o ruta local |
| `CLIP_LOCAL_DIR` | `../models/clip-vit-base-patch32` | Relativo a `api/` |
| `CLIP_ONNX_BACKEND` | `false` | `true` → intentar ONNX (`optimum`) con fallback a PyTorch |
| `EMBEDDING_DIM` | `512` | Debe coincidir con el indexado offline |

### Búsqueda

| Variable | Default | Notas |
|----------|---------|--------|
| `DEFAULT_TOP_K` | `50` | Tope global de resultados |
| `DEFAULT_PER_LAYER_LIMIT` | `100` | Tope por capa antes del merge |
| `DEFAULT_MIN_CONFIDENCE` | `0.0` | Umbral YOLO |
| `DEFAULT_SPATIAL_DISTANCE_M` | `50` | Radio por defecto en `search_spatial` |
| `MAX_SPATIAL_DISTANCE_M` | `500` | Tope de `spatial_distance_m` |
| `MAX_QUERY_LENGTH` | `500` | Tope de caracteres de `query` en `POST /search` |
