# Documentación de ARES (`doc/`)

Índice de la documentación del repositorio: guías de producto, preparación de datos y memoria técnica del TFM.

Para arrancar API y frontend, ver el [README del proyecto](../README.md). Base de datos (Docker Compose, esquema, SQL de ejemplo): [`db/README.md`](../db/README.md). Contratos HTTP, visor y CLI: [`api/README.md`](../api/README.md), [`frontend/README.md`](../frontend/README.md) y [`tools/README.md`](../tools/README.md).

## Contenidos

```
doc/
├── README.md                 # este índice
├── guia-de-uso.md            # cómo usar el visor de producto
├── preparacion-de-datos.md   # ortofoto → índice en PostgreSQL
├── cog-y-visor.md            # COG: construir, catálogo, ver en el mapa
└── memtech/                  # memoria técnica (capítulos Markdown)
    ├── 01-portada.md
    ├── 02-resumen.md
    ├── …
    └── 08-referencias.md
```

| Ruta | Para qué sirve |
|------|----------------|
| [`guia-de-uso.md`](guia-de-uso.md) | Usar ARES desde el **frontend**: consultas en lenguaje natural, mapa, tabla, interpretación, filtros y chips espaciales. |
| [`preparacion-de-datos.md`](preparacion-de-datos.md) | Construir el **dataset de prueba** extremo a extremo: COG → tiles → YOLO → CLIP → PostgreSQL (PostGIS + pgvector). |
| [`cog-y-visor.md`](cog-y-visor.md) | **COGs**: construcción con GDAL, columna `cog_url` en el catálogo y publicación HTTP (Range + CORS) para la ortofoto en el mapa. |
| [`memtech/`](memtech/) | **Memoria técnica** del TFM en capítulos numerados (portada → referencias). |

## Qué leer según el objetivo

| Objetivo | Empieza por |
|----------|-------------|
| Probar el visor y hacer búsquedas | [`guia-de-uso.md`](guia-de-uso.md) |
| Indexar una ortofoto nueva | [`preparacion-de-datos.md`](preparacion-de-datos.md) (detalle CLI en [`tools/`](../tools/README.md)) |
| Ver la ortofoto COG en el mapa | [`cog-y-visor.md`](cog-y-visor.md) |
| Entender el diseño y el relato del TFM | [`memtech/`](memtech/) desde el capítulo 02 |
| Endpoints y configuración de la API | [`api/README.md`](../api/README.md) (fuera de `doc/`) |
| Arranque y env del frontend | [`frontend/README.md`](../frontend/README.md) (fuera de `doc/`) |
| PostgreSQL / PostGIS / pgvector | [`db/README.md`](../db/README.md) (fuera de `doc/`) |
