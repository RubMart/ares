# Documentación de ARES (`doc/`)

Índice de la documentación del repositorio: guías de producto, preparación de datos, capturas de interfaz y memoria técnica del TFM.

Para arrancar API y frontend, ver el [README del proyecto](../README.md). Contratos HTTP y CLI: [`api/README.md`](../api/README.md) y [`tools/README.md`](../tools/README.md).

## Contenidos

```
doc/
├── README.md                 # este índice
├── guia-de-uso.md            # cómo usar el visor de producto
├── preparacion-de-datos.md   # ortofoto → índice en PostgreSQL
├── .images/                  # capturas referenciadas por las guías
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
| [`.images/`](.images/) | Capturas de la interfaz (zona de búsqueda, mapa, historial, etc.) incrustadas en las guías y en el README raíz. |
| [`memtech/`](memtech/) | **Memoria técnica** del TFM en capítulos numerados (portada → referencias). |

## Cómo visualizarlos

Todo el material de `doc/` es **Markdown** (más PNG en `.images/`). No hay generador de sitio propio en el repo: se lee en el IDE, en GitHub/GitLab o con un visor Markdown externo.

### En Cursor / VS Code

1. Abre el `.md` desde el explorador.
2. Vista previa: `Ctrl+Shift+V`, o panel al lado con `Ctrl+K` y luego `V`.
3. Las imágenes relativas (p. ej. `.images/ares_map_interface.png`) se resuelven desde la carpeta del documento.

### En GitHub (u otro hosting git)

Navega a [`doc/`](.) en el árbol del repositorio: el README de esta carpeta aparece como portada; cada `.md` se renderiza con títulos, tablas, diagramas Mermaid (si el hosting lo soporta) e imágenes.

### Memoria técnica (`memtech/`)

Léela **en orden numérico** de los ficheros:

| # | Capítulo |
|---|----------|
| 01 | [Portada](memtech/01-portada.md) |
| 02 | [Resumen](memtech/02-resumen.md) |
| 03 | [Introducción](memtech/03-introduccion.md) |
| 04 | [Descripción de la solución](memtech/04-descripcion-solucion.md) |
| 05 | [Implementación](memtech/05-implementacion.md) |
| 06 | [Resultados](memtech/06-resultados.md) |
| 07 | [Conclusiones](memtech/07-conclusiones.md) |
| 08 | [Referencias](memtech/08-referencias.md) |

Para un PDF o un único documento, puedes concatenar los capítulos o abrirlos en un editor que exporte Markdown → PDF (p. ej. Pandoc). El repo no incluye ese paso automatizado.

### Capturas (`.images/`)

No hace falta abrirlas a mano: están enlazadas desde [`guia-de-uso.md`](guia-de-uso.md) y desde el [README raíz](../README.md). Si quieres revisarlas sueltas, ábrelas desde el explorador de archivos o desde `.images/` en el hosting git.

## Qué leer según el objetivo

| Objetivo | Empieza por |
|----------|-------------|
| Probar el visor y hacer búsquedas | [`guia-de-uso.md`](guia-de-uso.md) |
| Indexar una ortofoto nueva | [`preparacion-de-datos.md`](preparacion-de-datos.md) (detalle CLI en [`tools/`](../tools/README.md)) |
| Entender el diseño y el relato del TFM | [`memtech/`](memtech/) desde el capítulo 02 |
| Endpoints y configuración de la API | [`api/README.md`](../api/README.md) (fuera de `doc/`) |
