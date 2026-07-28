# ARES

**AI Retrieval of Entities in Space**

ARES convierte las detecciones de objetos en imágenes aéreas en un índice **semántico y espacial** que se consulta en lenguaje natural. En lugar de montar filtros GIS o escribir SQL, el usuario formula la pregunta —en español o en inglés— y recibe las entidades georreferenciadas sobre un mapa.

Ejemplos: «piscinas», «coches rojos», «paneles solares cerca de edificios». El sistema interpreta la frase, recupera las detecciones pertinentes (clase, similitud visual y, si aplica, proximidad) y las entrega como GeoJSON listo para visualizar.

El recorrido de extremo a extremo es:

1. **Indexado offline.** Las ortofotos se procesan con YOLO y CLIP; las detecciones se cargan en PostgreSQL (PostGIS + pgvector).
2. **Búsqueda híbrida.** La API interpreta la consulta (parser determinista u Ollama), embebe el texto con CLIP y consulta la base: filtro por clase, ranking semántico y, cuando procede, proximidad espacial (`ST_DWithin`).
3. **Visor.** El frontend ([`frontend/`](frontend/)) muestra resultados en mapa y tabla, junto con la interpretación de la consulta para que el usuario pueda validarla.

![Interfaz de ARES: mapa con detecciones y filtros](doc/.images/ares_map_interface.png)

## Qué problema resuelve

Las ortofotos de alta resolución concentran mucha información territorial —vehículos, edificios, infraestructuras—, pero acceder a ella suele exigir herramientas GIS, catálogos rígidos o conocimiento de la base de datos. Quien no domina ese entorno tiene difícil preguntar algo tan directo como «¿dónde hay coches rojos?» o «¿qué paneles solares están cerca de edificios?».

ARES reduce esa barrera: las detecciones ya indexadas pasan a ser un índice consultable con frases naturales. El resultado es un GeoJSON apto para mapa y tabla, sin construir filtros a mano.

## Funcionalidades principales

### Consulta en lenguaje natural

El usuario escribe la pregunta en español o en inglés. La API la estructura en intención, clase objetivo (*target*), atributos opcionales y, si aplica, referencia espacial (*reference*) y relación (`near`). No hace falta conocer el esquema de la base ni los nombres internos de las clases YOLO.

Ejemplos típicos:

| Consulta | Comportamiento |
|----------|----------------|
| `piscinas` | Búsqueda por clase (suele resolverse sin LLM) |
| `coches rojos` | Clase + atributo de color vía ranking CLIP |
| `coches cerca de rotonda` | Espacial: *target* próximo a *reference* |
| `cars near buildings` | Igual en inglés |

### Búsqueda híbrida (clase + semántica)

Combina dos señales complementarias:

- **Filtro categórico** por clase YOLO cuando el catálogo permite asociar la consulta a una clase conocida.
- **Ranking semántico** con embeddings CLIP (`pgvector`): el texto embebido es solo *target* + atributos (no la frase espacial completa), alineado con los embeddings de imagen generados en el pipeline offline.

Así se puede pedir «coches» (clase) o matizar con «coches rojos» (clase + similitud visual).

### Consultas espaciales enriquecidas

Para frases del tipo «X cerca de Y», ARES distingue objetivo y referencia, aplica la relación `near` con un radio en metros (por defecto 50 m; máximo 500) y resuelve la proximidad con PostGIS (`ST_DWithin`). En la respuesta GeoJSON aparecen, cuando corresponde, la distancia a la referencia (`distance_to_reference_m`) y las *features* de referencia para pintarlas en una capa aparte del mapa.

También se pueden forzar *target*, *reference*, relación y distancia mediante **overrides** en `POST /search`, con prioridad sobre el analizador de texto.

### Interpretación inteligente y explicable

El orden de resolución de la consulta es fijo:

1. **Overrides HTTP** — parámetros explícitos → sin Ollama.
2. **Parser determinista** — coincidencia inequívoca con el catálogo (± color ± espacial) → sin Ollama (`llm_ms=0`).
3. **Caché LRU** o **Ollama** — solo si la frase es ambigua; la fuente queda registrada (`override` \| `parser` \| `cache` \| `llm`).

API y frontend exponen esa interpretación (*Más info*): intención, clases, atributos, distancia usada y un resumen en lenguaje natural, para validar o corregir lo que el sistema entendió.

### Pipeline de indexado offline

Desde una ortofoto hasta el índice consultable, en [`tools/`](tools/): detección YOLO, embeddings CLIP, thumbnails y carga a PostgreSQL (PostGIS + pgvector). Guía paso a paso: [`doc/preparacion-de-datos.md`](doc/preparacion-de-datos.md).

### Visor de producto

El frontend ([`frontend/`](frontend/)) ofrece la experiencia de uso completa:

- Búsqueda con texto libre, chips de ejemplo, número de resultados y filtro de baja confianza.
- Indicador de estado de la API y catálogo de capas con control de visibilidad.
- Mapa OpenLayers (detecciones + referencias espaciales; basemap calles / satélite).
- Filtros en cliente (capa, clase, confianza, similitud CLIP) sin relanzar la búsqueda.
- Tabla de resultados, descarga GeoJSON e interpretación visible.
- Interfaz bilingüe (ES/EN).

### API REST

[`api/`](api/) expone, entre otros, `GET /health`, `GET /catalog`, `POST /search` (GeoJSON + metadatos de interpretación) y gestión de la caché LLM (`GET`/`DELETE /cache/llm`). Incluye rate limiting en la búsqueda. Contrato y configuración: [`api/README.md`](api/README.md).

## Fortalezas frente a otras soluciones

Frente a visores GIS clásicos, APIs cloud de visión o stacks que exigen GPU y modelos en la nube, ARES apuesta por un despliegue **local, ligero y explicable**:

- **Todo en CPU.** YOLO, CLIP, Ollama y la API corren sin GPU. Sirve en portátiles y servidores modestos; la aceleración hardware es opcional.
- **Datos y consultas en local.** No depende de APIs cloud de visión ni de LLM externos: PostgreSQL, CLIP y Ollama viven en tu infraestructura. Encaja cuando la ortofoto o las detecciones no pueden salir del entorno.
- **Lenguaje natural y espacio a la vez.** No se queda en filtros por clase ni en búsqueda solo vectorial: combina clase YOLO, ranking CLIP y proximidad PostGIS (`cerca de`), en español e inglés.
- **LLM solo cuando hace falta.** Consultas inequívocas (`piscinas`, `coches cerca de rotonda`) las resuelve un parser determinista sin llamar a Ollama (`llm_ms=0`): menos latencia y menos dependencia del modelo.
- **Modelo pequeño y asequible.** El LLM por defecto (`llama3.2:3b`) cabe en hardware corriente; no hace falta un modelo grande ni una suscripción.
- **Interpretación visible.** API y frontend muestran cómo se entendió la frase (*target*, *reference*, distancia, fuente `parser` / `llm` / …). El usuario puede comprobar o corregir la intención, en lugar de tratar el sistema como caja negra.
- **Pipeline abierto de extremo a extremo.** De la ortofoto al mapa (tools + API + frontend), con GeoJSON estándar y stack open source, sin atarse a un producto GIS propietario.

## Stack

| Capa | Tecnología |
|------|------------|
| Detección / indexado (offline) | YOLO + CLIP en [`tools/`](tools/) |
| Base de datos | PostgreSQL + PostGIS + pgvector |
| Interpretación de consultas | Parser determinista + Ollama (`llama3.2:3b` por defecto) |
| API | FastAPI ([`api/`](api/)) |
| Frontend (visor) | Next.js + OpenLayers ([`frontend/`](frontend/)) |
| Visor de testing (API) | HTML/JS estático ([`api_webviewer/`](api_webviewer/)) — secundario |

## Estructura del repositorio

```
ares/
├── api/                 # API REST de búsqueda semántica / espacial
├── frontend/            # Visor de producto (Next.js + OpenLayers)
├── api_webviewer/       # Visor de testing de la API (mapa, tabla, JSON)
├── db/                  # PostgreSQL + PostGIS + pgvector (Docker Compose)
├── tools/               # Pipeline offline: detección, embeddings, SQL
├── models/              # Pesos YOLO/CLIP locales (ver README; `.pt` fuera de git)
├── doc/                 # Guía de uso, capturas y memoria técnica
├── AGENTS.md            # Contexto operativo para agentes / desarrollo
├── LICENSE              # GPL-3.0
└── .cursor/plans/       # Decisiones de diseño ya tomadas
```

## Arranque rápido

Antes de arrancar API o frontend hace falta una **base de datos PostgreSQL** con PostGIS y pgvector, con el catálogo de capas y las tablas de detecciones ya cargadas. Sin ese índice no hay resultados que consultar.

Arranque local con Docker Compose, esquema de tablas y SQL de ejemplo: [`db/README.md`](db/README.md). Para crear el índice desde una ortofoto: [`doc/preparacion-de-datos.md`](doc/preparacion-de-datos.md); CLI en [`tools/`](tools/).

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

Con la API en marcha:

```powershell
cd frontend
copy .env.example .env.local
npm install
npm run dev
```

Abre `http://127.0.0.1:3000`. La URL de la API se configura en `NEXT_PUBLIC_API_URL` (`.env.local`; por defecto `http://127.0.0.1:8000`).

Detalle de estructura, variables de entorno y scripts: [`frontend/README.md`](frontend/README.md).

### Visor de testing (`api_webviewer`)

Herramienta **secundaria** para probar la API a mano (mapa, tabla y JSON crudo). No es el frontend de producto ni tiene propósito público.

```powershell
cd api_webviewer
python -m http.server 8080
```

Abre `http://localhost:8080`. URL de la API en la cabecera del visor o en `api_webviewer/js/api.js`. Detalle: [`api_webviewer/README.md`](api_webviewer/README.md).

## Documentación

Índice de `doc/` (contenidos y para qué sirven): [`doc/README.md`](doc/README.md).

### Uso del producto

| Guía | Ruta | Para qué |
|------|------|----------|
| **Guía de uso** | [`doc/guia-de-uso.md`](doc/guia-de-uso.md) | Buscar desde el frontend: consultas, mapa, filtros, interpretación |
| **Preparación de datos** | [`doc/preparacion-de-datos.md`](doc/preparacion-de-datos.md) | Crear el índice desde una ortofoto (COG → tiles → YOLO → CLIP → PostgreSQL) |

### API y desarrollo

| Guía | Ruta | Para qué |
|------|------|----------|
| **API reference** | [`api/README.md`](api/README.md) | Endpoints, `POST /search`, configuración y tests |
| **OpenAPI** | `http://127.0.0.1:8000/docs` | Documentación interactiva (con la API en marcha) |
| **Frontend** | [`frontend/README.md`](frontend/README.md) | Visor de producto: estructura, env, arranque |
| **Base de datos** | [`db/README.md`](db/README.md) | PostGIS + pgvector, tablas, SQL de ejemplo, Docker Compose |
| **Visor de testing** | [`api_webviewer/README.md`](api_webviewer/README.md) | Cliente estático HTML/JS para depurar la API |
| **Pipeline offline** | [`tools/README.md`](tools/README.md) | CLI de detección, embeddings y carga a PostgreSQL |
| **Memoria técnica** | [`doc/memtech/`](doc/memtech/) | Narrativa del TFM |

## Licencia

El código de ARES se distribuye bajo [**GNU General Public License v3.0**](LICENSE) (GPL-3.0).
