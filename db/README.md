# Base de datos (PostgreSQL + PostGIS + pgvector)

Índice espacial y semántico de ARES: catálogo de capas y tablas de detecciones con geometría (`PostGIS`) y embedding CLIP (`pgvector`).

La imagen Docker vive en esta carpeta (`Dockerfile` + `docker-compose.yml`). El schema del catálogo está en [`sql/`](sql/). Cada **capa de detecciones** (DDL + datos) la genera el pipeline offline en [`../tools/`](../tools/) (`embed2psql.py`) con el nombre que elijas en `--layer`.

Índice del monorepo: [`../README.md`](../README.md).

## Dependencias

### En el host (arranque local)

| Componente | Uso |
|------------|-----|
| [Docker](https://docs.docker.com/get-docker/) | Construir y ejecutar el contenedor |
| [Docker Compose](https://docs.docker.com/compose/) v2 (`docker compose`) | Orquestar el servicio `db` |
| `psql` (opcional) | Cliente para cargar SQL y verificar |

Sin Docker, sirve cualquier PostgreSQL **14+** con las mismas extensiones (ver abajo); la API y los ejemplos asumen por defecto la BD `detecciones`.

### Extensiones / módulos dentro de PostgreSQL

La imagen se basa en `pgvector/pgvector:pg17` y añade los paquetes PostGIS:

| Módulo | Paquete / extensión | Rol en ARES |
|--------|---------------------|-------------|
| **PostgreSQL 17** | imagen base | Motor relacional |
| **pgvector** | `CREATE EXTENSION vector` | Tipo `vector(512)` y operador de distancia coseno `<=>` |
| **PostGIS 3** | `postgresql-17-postgis-3` (+ scripts) → `CREATE EXTENSION postgis` | `GEOMETRY`, `ST_MakeEnvelope`, `ST_DWithin`, `ST_AsGeoJSON`, índices GIST |

Tras el primer arranque hay que crear las extensiones en la BD de trabajo (también lo hacen los `*_schema.sql`):

```sql
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS vector;
```

### Cliente de la API (no va en el contenedor)

La API habla con esta BD vía `asyncpg` / SQLAlchemy. Dependencias Python en [`../api/requirements.txt`](../api/requirements.txt) (`asyncpg`, `pgvector`, `geoalchemy2`, …). URL típica en `api/.env`: ver [Conexión desde la API](#conexión-desde-la-api).

## Modelo de datos

Hay **una tabla de catálogo** y **una tabla de detecciones por capa**. El nombre de cada capa en el catálogo (`nombre_capa`) coincide con el nombre de su tabla. Quién despliega la solución elige esos nombres (y cuántas capas hay) según sus datos; no hay un nombre de capa fijo en el producto.

```mermaid
erDiagram
    detecciones_catalogo ||--o{ capa_detecciones : "nombre_capa = tabla"
    detecciones_catalogo {
        serial id PK
        varchar nombre_capa UK
        geometry bbox
        text cog_url
        int total_detecciones
        int total_tiles
        jsonb metadata
    }
    capa_detecciones {
        serial id PK
        varchar tile_id
        varchar clase_yolo
        varchar modelo_deteccion
        vector embedding
        geometry geom
        float confianza
        jsonb metadata
    }
```

### `detecciones_catalogo`

Índice de capas descubiertas por `GET /catalog` y por la búsqueda multi-capa. Schema versionado en [`sql/detecciones_catalogo_schema.sql`](sql/detecciones_catalogo_schema.sql).

| Columna | Tipo | Notas |
|---------|------|--------|
| `id` | `SERIAL` PK | |
| `nombre_capa` | `VARCHAR` UNIQUE | Nombre de la tabla de detecciones |
| `bbox` | `GEOMETRY(Polygon, 3857)` | Extensión de la capa |
| `cog_url` | `TEXT` | Ruta/URL del COG de referencia |
| `total_detecciones` | `INTEGER` | Filas cargadas |
| `total_tiles` | `INTEGER` | Tiles procesados |
| `metadata` | `JSONB` | Auxiliar (`{}` por defecto) |

Índice: GIST sobre `bbox`.

### Tabla de detecciones (por capa)

Una tabla por capa, con la misma estructura; solo cambia el identificador (`--layer` en `embed2psql.py`). El DDL de cada capa lo emite el pipeline; no se versiona aquí un schema de capa concreto.

| Columna | Tipo | Notas |
|---------|------|--------|
| `id` | `SERIAL` PK | |
| `tile_id` | `VARCHAR` | Layout XYZ, p. ej. `16/32090/24688` |
| `clase_yolo` | `VARCHAR` | Clase canónica del detector |
| `modelo_deteccion` | `VARCHAR` | Peso/origen YOLO |
| `embedding` | `vector(512)` | CLIP imagen, normalizado L2 |
| `geom` | `GEOMETRY(Polygon, 3857)` | Bbox de la detección en Web Mercator |
| `confianza` | `FLOAT` | Score del detector |
| `metadata` | `JSONB` | Auxiliar |

Índices típicos:

- GIST en `geom` (filtros espaciales / `ST_DWithin`)
- B-tree en `modelo_deteccion`
- HNSW en `embedding` con `vector_cosine_ops` (ranking `<=>`)

EPSG:3857 alinea tiles `gdal2tiles` con distancias en metros a escala urbana.

## SQL (`sql/`)

| Fichero | Contenido |
|---------|-----------|
| [`sql/detecciones_catalogo_schema.sql`](sql/detecciones_catalogo_schema.sql) | DDL del catálogo |

Los schemas y datos de cada **capa de detecciones** salen de `tools/embed2psql.py` (ficheros `{capa}_schema.sql` y `{capa}_data.sql`, más el registro en catálogo).

### Esquema catálogo

```sql
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS detecciones_catalogo (
    id                SERIAL PRIMARY KEY,
    nombre_capa       VARCHAR NOT NULL UNIQUE,
    bbox              GEOMETRY(Polygon, 3857) NOT NULL,
    cog_url           TEXT NOT NULL,
    total_detecciones INTEGER NOT NULL,
    total_tiles       INTEGER NOT NULL,
    metadata          JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_detecciones_catalogo_bbox
    ON detecciones_catalogo USING GIST (bbox);
```

### Esquema de una capa de detecciones (genérico)

Sustituye `{capa}` por el nombre elegido (debe coincidir con `nombre_capa` en el catálogo):

```sql
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS {capa} (
    id               SERIAL PRIMARY KEY,
    tile_id          VARCHAR NOT NULL,
    clase_yolo       VARCHAR NOT NULL,
    modelo_deteccion VARCHAR NOT NULL,
    embedding        vector(512) NOT NULL,
    geom             GEOMETRY(Polygon, 3857) NOT NULL,
    confianza        FLOAT NOT NULL,
    metadata         JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_{capa}_geom
    ON {capa} USING GIST (geom);

CREATE INDEX IF NOT EXISTS idx_{capa}_modelo
    ON {capa} (modelo_deteccion);

CREATE INDEX IF NOT EXISTS idx_{capa}_embedding
    ON {capa} USING hnsw (embedding vector_cosine_ops);
```

### Datos (INSERT)

Los `*_data.sql` (filas de detecciones + `INSERT` en catálogo) se generan con el pipeline y se cargan con `psql`:

```powershell
cd tools
python embed2psql.py `
  --layer <nombre_capa> `
  --cog-path <ruta-al-cog.tif> `
  --batch <ruta-a-tiles> `
  --output-dir <salida-sql>
```

Orden habitual de carga:

```powershell
psql $URL -f db/sql/detecciones_catalogo_schema.sql
psql $URL -f <salida-sql>/<nombre_capa>_schema.sql
psql $URL -f <salida-sql>/<nombre_capa>_data.sql
psql $URL -f <salida-sql>/detecciones_catalogo_data.sql
```

Detalle del flujo (YOLO → CLIP → SQL): [`../tools/README.md`](../tools/README.md) y [`../doc/preparacion-de-datos.md`](../doc/preparacion-de-datos.md).

## Arranque local con Docker Compose

Para el **stack completo** (BD + Ollama + API + frontend) usa el [`docker-compose.yml`](../docker-compose.yml) de la raíz del repo (ver [`../README.md`](../README.md)). Esta carpeta sirve para levantar **solo** PostgreSQL. No publiques a la vez ambos Compose en el puerto **7432**.

Ficheros en esta carpeta:

| Fichero | Rol |
|---------|-----|
| `Dockerfile` | `pgvector/pgvector:pg17` + PostGIS 3 |
| `docker-compose.yml` | Servicio `db`, puerto host **7432**, volumen persistente |
| `sql/` | Schema del catálogo |

Valores por defecto del compose:

| Variable | Valor |
|----------|--------|
| Usuario | `user` |
| Contraseña | `password` |
| Base de datos | `embedding_db` |
| Puerto en el host | `7432` → `5432` en el contenedor |
| Volumen | `postgres_data` |

### Subir el servicio

Desde `db/` (PowerShell o bash):

```powershell
cd db
docker compose up -d --build
```

Equivalente con la CLI clásica: `docker-compose up -d --build`.

Comprobar estado:

```powershell
docker compose ps
docker compose logs -f db
```

Espera a ver que PostgreSQL acepta conexiones (`database system is ready to accept connections`).

### Conectar con `psql`

```powershell
psql "postgresql://user:password@localhost:7432/embedding_db"
```

O entrando al contenedor:

```powershell
docker compose exec db psql -U user -d embedding_db
```

### Crear extensiones (si aún no hay schema SQL)

```sql
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS vector;

SELECT postgis_full_version();
SELECT extname, extversion FROM pg_extension WHERE extname IN ('postgis', 'vector');
```

### Aplicar el schema del catálogo

```powershell
$env:PGPASSWORD = "password"
$URL = "postgresql://user:password@localhost:7432/embedding_db"

psql $URL -f db/sql/detecciones_catalogo_schema.sql
```

A continuación aplica el schema y los datos de cada capa generados por `tools/embed2psql.py` (ver [Datos (INSERT)](#datos-insert)).

### Parar / borrar

```powershell
docker compose down          # conserva el volumen
docker compose down -v       # borra también postgres_data
```

### Solo imagen Docker (sin Compose)

```powershell
cd db
docker build -t ares-postgres:pg17-postgis .
docker run -d --name ares-db `
  -p 7432:5432 `
  -e POSTGRES_USER=user `
  -e POSTGRES_PASSWORD=password `
  -e POSTGRES_DB=embedding_db `
  -v ares_pgdata:/var/lib/postgresql/data `
  ares-postgres:pg17-postgis
```

## Conexión desde la API

Con el Compose por defecto de esta carpeta, en `api/.env`:

```env
DATABASE_URL=postgresql+asyncpg://user:password@localhost:7432/embedding_db
CATALOG_TABLE=detecciones_catalogo
```

Los defaults de [`../api/.env.example`](../api/.env.example) (`postgres:postgres@localhost:5432/detecciones`) apuntan a un PostgreSQL nativo distinto. Ajusta usuario, contraseña, puerto y nombre de BD para que coincidan con tu instancia (Docker o local).

Si prefieres alinear el Compose con esos defaults, cambia en `docker-compose.yml` las variables `POSTGRES_*` y el mapeo de puertos, recrea el volumen (`docker compose down -v`) y vuelve a cargar el SQL.

## Verificación rápida

Sustituye `<nombre_capa>` por la tabla registrada en el catálogo:

```sql
SELECT nombre_capa, total_detecciones, total_tiles, cog_url
FROM detecciones_catalogo;

SELECT clase_yolo, COUNT(*) AS n
FROM <nombre_capa>
GROUP BY 1
ORDER BY n DESC
LIMIT 20;

SELECT tile_id, clase_yolo, confianza,
       ST_AsText(ST_Transform(ST_Centroid(geom), 4326)) AS centro_wgs84
FROM <nombre_capa>
LIMIT 5;
```

Con la API en marcha: `GET /catalog` debe listar las capas cargadas y `POST /search` con una consulta del dominio (p. ej. `{"query": "piscinas"}`) debe devolver features si hay datos indexados.
