---
name: API búsqueda semántica
overview: "Diseño de una API REST FastAPI con Clean Architecture en `api/` para búsqueda semántica de detecciones geoespaciales: análisis LLM bilingüe (ES/EN), vectorización CLIP compatible con `embed.py`, query híbrida (filtro por clase + ranking coseno) sobre todas las capas del catálogo, y respuesta GeoJSON."
todos:
  - id: scaffold-api
    content: Crear estructura api/ con config.py, main.py, requirements.txt (ver sección Dependencias) y capas domain/application/infrastructure/api
    status: completed
  - id: domain-layer
    content: Definir entidades Detection/CatalogLayer, StructuredQuery, e interfaces ABC de repositorios y servicios IA
    status: completed
  - id: infra-db
    content: Implementar session async (asyncpg), modelo SQLModel del catálogo y PostgresDetectionRepository con query dinámica multi-capa
    status: completed
  - id: infra-ai
    content: Implementar OpenAIQueryAnalyzer bilingüe (ES/EN) con catálogo estático clase_yolo y ClipOnnxTextEmbedder compatible con embed.py
    status: completed
  - id: use-case-search
    content: "Implementar SearchDetectionsUseCase: LLM → CLIP → query híbrida → fusión → GeoJSON"
    status: completed
  - id: api-routes
    content: Exponer POST /search, GET /catalog, GET /health con schemas Pydantic y dependencies
    status: completed
  - id: manual-test
    content: "Probar contra BBDD con sql_test cargado: búsquedas ES ('piscinas', 'coches') y EN ('pools', 'cars'), validar GeoJSON en OpenLayers"
    status: completed
isProject: false
---

# Plan: API REST de búsqueda semántica geoespacial

## Contexto confirmado

**Base de datos** (fuente de verdad: [`sql_test/`](D:\TFM\yolo_example\sql_test)):

| Tabla | Rol |
|-------|-----|
| `detecciones_catalogo` | Índice de capas: `nombre_capa` → nombre de tabla de detecciones |
| `{nombre_capa}` (ej. `madrid_detections_example`) | Detecciones con `embedding vector(512)`, `geom GEOMETRY(Polygon, 3857)`, `clase_yolo`, `modelo_deteccion`, `confianza` |

**Pipeline existente**: [`embed.py`](D:\TFM\yolo_example\embed.py) genera embeddings de imagen con `openai/clip-vit-base-patch32`, proyección visual y **normalización L2**. Dimensión: **512**. Índice HNSW con `vector_cosine_ops` en [`madrid_detections_example_schema.sql`](D:\TFM\yolo_example\sql_test\madrid_detections_example_schema.sql).

**Decisiones del usuario**:
- Driver DB: **asyncpg** (async real)
- Filtro de clase: **lista de `clase_yolo`** canónicas (no `class_id`)
- Query híbrida: **filtro duro por clase + ranking por similitud coseno**
- Alcance: **todas las capas** del catálogo, fusionando resultados
- Idioma de consulta: **español o inglés** (bilingüe; el usuario no indica idioma explícitamente)

---

## Soporte bilingüe (ES / EN)

La consulta original (`query`) puede llegar en **español o inglés** sin parámetro adicional de idioma. El sistema debe interpretarla correctamente en ambos casos.

**Principio**: el LLM normaliza el intent a un concepto canónico; CLIP recibe el **texto original** del usuario (sin traducir) para el ranking semántico, ya que `clip-vit-base-patch32` entiende ambos idiomas en el espacio de embeddings.

| Capa | Responsabilidad bilingüe |
|------|--------------------------|
| `OpenAIQueryAnalyzer` | Detectar idioma (`es` / `en`), interpretar sinónimos en ambos idiomas, mapear a `clase_yolo` |
| `yolo_class_catalog.py` | Catálogo estático con sinónimos ES + EN → lista de `clase_yolo` |
| `ClipOnnxTextEmbedder` | Vectorizar `query` tal cual (ES o EN); no traducir antes de embeddar |
| `StructuredQuery` | Incluir `detected_language` y `canonical_label` (inglés, alineado con nombres YOLO) |

---

## Arquitectura (Clean Architecture)

```mermaid
flowchart TB
    subgraph api_layer [api/]
        Router["routes/search.py"]
        Schemas["schemas/search.py"]
    end
  subgraph app_layer [application/]
        UC["SearchDetectionsUseCase"]
        DTO["SearchQuery / SearchResult"]
    end
  subgraph domain_layer [domain/]
        Det["Detection"]
        Cat["CatalogLayer"]
        RepoIF["DetectionRepository ABC"]
        EmbedIF["TextEmbedder ABC"]
        LLMIF["QueryAnalyzer ABC"]
    end
  subgraph infra_layer [infrastructure/]
        PgRepo["PostgresDetectionRepository"]
        CLIP["ClipOnnxTextEmbedder"]
        GPT["OpenAIQueryAnalyzer"]
        Geo["GeoJsonSerializer"]
    end

    Router --> UC
    UC --> LLMIF
    UC --> EmbedIF
    UC --> RepoIF
    PgRepo -.-> RepoIF
    CLIP -.-> EmbedIF
    GPT -.-> LLMIF
    UC --> Geo
```

### Estructura de carpetas en [`api/`](D:\TFM\yolo_example\api)

```
api/
├── config.py                  # Toda la configuración del proyecto
├── main.py                    # FastAPI app, lifespan, CORS
├── requirements.txt
├── domain/
│   ├── entities/
│   │   ├── detection.py
│   │   └── catalog_layer.py
│   ├── value_objects/
│   │   ├── semantic_query.py  # StructuredQuery del LLM
│   │   └── search_filters.py
│   └── repositories/
│       ├── catalog_repository.py      # ABC
│       └── detection_repository.py    # ABC
├── application/
│   ├── dto/
│   │   └── search_dto.py
│   └── use_cases/
│       └── search_detections.py
├── infrastructure/
│   ├── db/
│   │   ├── session.py         # async engine + asyncpg
│   │   ├── models.py          # SQLModel: CatalogLayerORM
│   │   └── postgres_detection_repository.py
│   ├── ai/
│   │   ├── clip_text_embedder.py   # sentence-transformers + ONNX
│   │   ├── openai_query_analyzer.py
│   │   └── yolo_class_catalog.py   # mapeo estático clase_yolo
│   └── geo/
│       └── geojson_serializer.py
└── api/
    ├── dependencies.py        # inyección de dependencias
    ├── routes/
    │   ├── search.py
    │   └── catalog.py         # listar capas disponibles
    └── schemas/
        ├── search.py          # request/response Pydantic
        └── geojson.py         # FeatureCollection tipado
```

---

## Flujo del caso de uso `SearchDetections`

```mermaid
sequenceDiagram
    participant Client
    participant API
    participant LLM as GPT35_Analyzer
    participant CLIP as CLIP_ONNX_Text
    participant DB as PostgreSQL

    Client->>API: POST /search {"query": "piscinas" | "swimming pools"}
    API->>LLM: Analizar consulta ES/EN + mapear clase_yolo
    LLM-->>API: StructuredQuery{intent, clase_yolo[], language, raw_query}
    API->>CLIP: embed_text(query original sin traducir)
    CLIP-->>API: vector[512] L2-normalizado
    API->>DB: SELECT capas FROM detecciones_catalogo
    loop cada nombre_capa
        API->>DB: WHERE clase_yolo IN (...) ORDER BY embedding <=> vec LIMIT k
    end
    DB-->>API: filas con geom + similarity
    API->>API: fusionar, re-ordenar, truncar top-N
    API-->>Client: GeoJSON FeatureCollection
```

### Paso 1 — Análisis semántico (LLM)

Implementar `OpenAIQueryAnalyzer` con `langchain_openai.ChatOpenAI(model="gpt-3.5-turbo")` y salida estructurada (Pydantic / `with_structured_output`):

```python
class StructuredQuery(BaseModel):
    intent: Literal["search_class", "search_attribute", "unknown"]
    detected_language: Literal["es", "en", "unknown"]
    object_label: str | None          # etiqueta en idioma detectado, ej. "piscina" o "pool"
    canonical_label: str | None       # concepto normalizado en inglés, ej. "swimming pool"
    clase_yolo_candidates: list[str]  # ej. ["swimming_pool", "swimming pool"]
    attributes: list[str]             # vacío si no importan
    reasoning: str                    # trazabilidad
```

El **system prompt** indicará explícitamente que la consulta puede estar en **español o inglés** y debe:
1. Detectar el idioma de entrada
2. Normalizar el concepto a un `canonical_label` en inglés (alineado con nombres YOLO)
3. Resolver `clase_yolo_candidates` usando el catálogo estático (`yolo_class_catalog.py`)

Catálogo estático bilingüe (derivado de [`detection_summary.json`](D:\TFM\yolo_example\pruebas\tiles16\detection_summary.json)):

| Sinónimos ES | Sinónimos EN | `clase_yolo` en BBDD |
|--------------|--------------|----------------------|
| piscina, piscinas, alberca | pool, pools, swimming pool | `swimming_pool`, `swimming pool` |
| coche, coches, automóvil, vehículo | car, cars, vehicle, vehicles | `car`, `small vehicle`, `large vehicle`, `van`, `truck`, `bus`, `motor` |
| edificio, edificios, construcción | building, buildings | `Building`, `building` |
| panel solar, placas solares, fotovoltaico | solar panel, photovoltaic, solar farm | `photovoltaic panel` |
| campo de fútbol, campo deportivo, pista de baloncesto | soccer field, sports field, basketball court | `soccer ball field`, `basketball court` |
| peatón, peatones | pedestrian, pedestrians | `pedestrian` |
| rotonda, glorieta | roundabout, traffic circle | `roundabout` |

Ejemplos de salida esperada del LLM:
- `"piscinas"` → `detected_language="es"`, `canonical_label="swimming pool"`, `clase_yolo_candidates=["swimming_pool","swimming pool"]`
- `"swimming pools"` → `detected_language="en"`, mismo mapeo de clases
- `"find cars near buildings"` → `intent="search_class"` para el objeto principal; atributos espaciales fuera de v1

Si `intent != "search_class"` o no hay candidatos, el API devuelve `400` con mensaje claro (no inventar resultados).

### Paso 2 — Embedding de texto (CLIP compatible)

**Requisito crítico**: el vector de consulta debe ser comparable con los embeddings de imagen en BBDD generados por [`embed.py`](D:\TFM\yolo_example\embed.py).

Estrategia en `ClipOnnxTextEmbedder`:
- Modelo base: `openai/clip-vit-base-patch32` (equivalente ST: `clip-ViT-B-32`)
- Backend: `sentence-transformers` con **ONNX Runtime** (`backend="onnx"` o export ONNX explícito)
- **Normalización L2** obligatoria antes de enviar a pgvector
- Validación en arranque: embedear texto de prueba y comprobar dimensión 512
- **Bilingüe**: embeddar la `query` original del usuario (ES o EN); no traducir previamente. CLIP alinea semánticamente consultas multilingües con los embeddings de imagen

> Nota: `embed.py` usa la rama **visual** (`vision_model` → `visual_projection`). Para consultas de texto usamos la rama **textual** del mismo modelo CLIP. Eso es el espacio semántico correcto para comparar con `<=>` coseno.

### Paso 3 — Query híbrida en PostgreSQL (todas las capas)

1. Leer todas las filas de `detecciones_catalogo` (`CatalogRepository`)
2. Validar `nombre_capa` contra regex `^[A-Za-z_][A-Za-z0-9_]*$` (misma regla que [`embed2psql.py`](D:\TFM\yolo_example\embed2psql.py)) para evitar SQL injection en nombres dinámicos
3. Por cada capa, ejecutar query parametrizada:

```sql
SELECT
    :layer_name AS layer,
    id, tile_id, clase_yolo, modelo_deteccion, confianza,
    ST_AsGeoJSON(geom) AS geom_json,
    1 - (embedding <=> CAST(:query_vec AS vector)) AS similarity
FROM {validated_table}
WHERE clase_yolo = ANY(:clase_yolo_list)
  AND (:min_conf IS NULL OR confianza >= :min_conf)
ORDER BY embedding <=> CAST(:query_vec AS vector)
LIMIT :per_layer_limit
```

4. Fusionar resultados de todas las capas, ordenar globalmente por `similarity DESC`, truncar a `top_k` global
5. Incluir en `properties` de cada Feature: `layer`, `similarity`, `clase_yolo`, `modelo_deteccion`, `confianza`, `tile_id`, `id`

**Filtro espacial opcional** (fase 2, no bloqueante): parámetro `bbox` en EPSG:3857 con `ST_Intersects(geom, ST_MakeEnvelope(...))`.

### Paso 4 — Salida GeoJSON

`GeoJsonSerializer` produce RFC 7946 compatible con OpenLayers:

```json
{
  "type": "FeatureCollection",
  "crs": { "type": "name", "properties": { "name": "EPSG:3857" } },
  "features": [
    {
      "type": "Feature",
      "id": "madrid_detections_example/123",
      "geometry": { "type": "Polygon", "coordinates": [...] },
      "properties": {
        "layer": "madrid_detections_example",
        "similarity": 0.87,
        "clase_yolo": "swimming_pool",
        "modelo_deteccion": "swimming-pool-detector",
        "confianza": 0.54,
        "tile_id": "16/32103/24712",
        "query": "piscinas"
      }
    }
  ],
  "metadata": {
    "query": "piscinas",
    "detected_language": "es",
    "structured_query": { ... },
    "total_features": 28,
    "layers_searched": ["madrid_detections_example"]
  }
}
```

OpenLayers acepta EPSG:3857 directamente si el mapa está en Web Mercator.

---

## Endpoints REST

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/health` | Estado API + conexión DB |
| `GET` | `/catalog` | Lista capas (`nombre_capa`, `cog_url`, bbox como GeoJSON) |
| `POST` | `/search` | Búsqueda semántica principal |

**Request `POST /search`** (consulta en ES o EN, sin campo `language`):
```json
{
  "query": "piscinas",
  "top_k": 50,
  "per_layer_limit": 100,
  "min_confidence": 0.25
}
```
```json
{
  "query": "swimming pools",
  "top_k": 50
}
```

**Response**: `application/geo+json` o `application/json` con FeatureCollection.

---

## [`config.py`](D:\TFM\yolo_example\api\config.py) — configuración centralizada

Usar `pydantic-settings` (`BaseSettings`):

```python
class Settings(BaseSettings):
    # App
    app_name: str = "detecciones-search-api"
    debug: bool = False
    cors_origins: list[str] = ["*"]

    # PostgreSQL (asyncpg)
    database_url: str  # postgresql+asyncpg://user:pass@host:5432/db

    # OpenAI
    openai_api_key: str
    openai_model: str = "gpt-3.5-turbo"
    openai_temperature: float = 0.0

    # CLIP
    clip_model_name: str = "clip-ViT-B-32"  # ≡ openai/clip-vit-base-patch32
    clip_onnx_backend: bool = True
    embedding_dim: int = 512

    # Búsqueda
    default_top_k: int = 50
    default_per_layer_limit: int = 100
    default_min_confidence: float = 0.0

    # Catálogo
    catalog_table: str = "detecciones_catalogo"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
```

Variables de entorno vía `.env` en `api/` (no commitear secretos).

---

## Dependencias (`api/requirements.txt`)

Fichero dedicado al API, **independiente** del [`requirements.txt`](D:\TFM\yolo_example\requirements.txt) raíz del pipeline YOLO/CLIP. Instalar en un venv dentro de `api/`:

```bash
cd api
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate
pip install -r requirements.txt
```

### Contenido de `api/requirements.txt`

```text
# --- Web API ---
fastapi>=0.115.0
uvicorn[standard]>=0.30.0

# --- Configuración y validación ---
pydantic>=2.7.0
pydantic-settings>=2.2.0
python-dotenv>=1.0.0

# --- Base de datos (PostgreSQL async + PostGIS + pgvector) ---
sqlmodel>=0.0.22
sqlalchemy[asyncio]>=2.0.0
asyncpg>=0.29.0
greenlet>=3.0.0
pgvector>=0.3.0
geoalchemy2>=0.15.0

# --- LLM: análisis semántico bilingüe (ES/EN) ---
langchain-openai>=0.2.0
langchain-core>=0.3.0
openai>=1.40.0

# --- CLIP texto: embeddings de consulta (compatible embed.py, ONNX) ---
sentence-transformers>=3.0.0
onnxruntime>=1.18.0
transformers>=4.40.0
huggingface-hub>=0.24.0

# --- Utilidades HTTP (health checks, TestClient) ---
httpx>=0.27.0
```

### Resumen por capa

| Paquete | Uso en el API |
|---------|----------------|
| `fastapi`, `uvicorn` | Servidor REST y routing |
| `pydantic`, `pydantic-settings` | Schemas request/response, `config.py`, salida estructurada LLM |
| `python-dotenv` | Cargar `.env` (`DATABASE_URL`, `OPENAI_API_KEY`, etc.) |
| `sqlmodel`, `sqlalchemy[asyncio]` | ORM async, modelos del catálogo |
| `asyncpg`, `greenlet` | Driver PostgreSQL async (sustituye `psycopg2-binary`) |
| `pgvector` | Tipo `vector(512)` y operador `<=>` en SQLAlchemy |
| `geoalchemy2` | Tipo `Geometry` para `bbox` / `geom` PostGIS |
| `langchain-openai`, `langchain-core`, `openai` | `ChatOpenAI` + `with_structured_output` para análisis de consulta |
| `sentence-transformers`, `onnxruntime` | CLIP texto con backend ONNX (`clip-ViT-B-32`) |
| `transformers`, `huggingface-hub` | Descarga del modelo CLIP al primer arranque |
| `httpx` | Cliente HTTP async; `TestClient` de FastAPI en pruebas |

### Dependencias de desarrollo (opcional, `api/requirements-dev.txt`)

```text
-r requirements.txt
pytest>=8.0.0
pytest-asyncio>=0.24.0
ruff>=0.6.0
```

### Notas de instalación

- **No incluir** `psycopg2-binary`: el acceso a BBDD es 100 % async vía `asyncpg`.
- **No incluir** `torch` ni `opencv-python`: el API no ejecuta YOLO ni CLIP visual; solo CLIP **texto** vía ONNX.
- La primera ejecución descargará el modelo `clip-ViT-B-32` desde HuggingFace (~400 MB); cache en `~/.cache/huggingface/`.
- `OPENAI_API_KEY` obligatoria en `.env` para el analizador LLM.
- `DATABASE_URL` formato: `postgresql+asyncpg://usuario:password@localhost:5432/nombre_bbdd`

### Ejemplo `.env` (referencia, no commitear)

```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/detecciones
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-3.5-turbo
CLIP_MODEL_NAME=clip-ViT-B-32
CLIP_ONNX_BACKEND=true
DEFAULT_TOP_K=50
DEFAULT_PER_LAYER_LIMIT=100
DEFAULT_MIN_CONFIDENCE=0.0
CATALOG_TABLE=detecciones_catalogo
CORS_ORIGINS=["*"]
DEBUG=false
```

---

## Inyección de dependencias y lifespan

En `main.py`:
- **Lifespan**: crear engine async, precargar modelo CLIP ONNX (evitar cold start por request), instanciar `ChatOpenAI`
- `dependencies.py`: factories para session, repositorios, use case
- Un único `SearchDetectionsUseCase` orquesta LLM → CLIP → DB → GeoJSON

---

## Consideraciones de seguridad y robustez

- **SQL dinámico**: solo nombres de tabla que existan en `detecciones_catalogo` y pasen regex; nunca interpolar input del usuario en identificadores
- **Capa inexistente en catálogo**: ignorar silenciosamente o log warning
- **LLM falla / timeout**: devolver `503` con detalle; no hacer fallback a búsqueda sin análisis
- **Sin candidatos clase_yolo**: `400 Bad Request`
- **Logging estructurado**: query original, structured_query, capas consultadas, latencias LLM/CLIP/DB

---

## Pruebas manuales previstas

1. `GET /health` con PostgreSQL cargado desde [`sql_test/*.sql`](D:\TFM\yolo_example\sql_test)
2. `POST /search {"query": "piscinas"}` → features con `swimming_pool` / `swimming pool`, `detected_language: "es"`
3. `POST /search {"query": "swimming pools"}` → mismas clases, `detected_language: "en"`
4. `POST /search {"query": "coches"}` y `{"query": "cars"}` → clases de vehículos VisDrone/DOTA
5. `POST /search {"query": "buildings"}` y `{"query": "edificios"}` → `Building` / `building`
6. Verificar que `similarity` decrece de forma coherente en ambos idiomas
7. Abrir respuesta en [`pruebas/tiles16/openlayers.html`](D:\TFM\yolo_example\pruebas\tiles16\openlayers.html) como smoke test visual

---

## Fuera de alcance (v1)

- Autenticación / rate limiting
- Filtro espacial por bbox (dejado preparado en repositorio)
- Caché de embeddings de consultas frecuentes
- Endpoint de ingesta (ya existe pipeline `detect → embed → embed2psql`)
