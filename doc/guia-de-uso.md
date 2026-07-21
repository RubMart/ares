# Guía de uso de ARES

Esta guía explica cómo usar ARES desde el **frontend** ([`frontend/`](../frontend/)), el visor de producto. Arranque y variables de entorno: [`frontend/README.md`](../frontend/README.md). Contrato HTTP: [API reference](../api/README.md).

> **Nota:** [`api_webviewer/`](../api_webviewer/) es un visor **secundario** solo para testing manual de la API (mapa, tabla y JSON). No es la interfaz de usuario principal.

## Requisitos previos

1. **Base de datos** PostgreSQL con PostGIS + pgvector y detecciones cargadas (catálogo + capas). Sin datos indexados, la búsqueda no devolverá entidades.
2. **API** en marcha (`uvicorn` en `api/`, por defecto `http://127.0.0.1:8000`).
3. **Frontend** en marcha (`npm run dev` desde `frontend/`, por defecto `http://127.0.0.1:3000`).
4. **Ollama** (recomendado) con el modelo configurado (`llama3.2:3b` por defecto). Las consultas inequívocas pueden resolverse sin LLM; las ambiguas sí lo necesitan.

Comprueba el estado en la cabecera del frontend (*API activa*) o con `GET /health`. El indicador debe mostrar la API activa antes de buscar.

## Panorama de la interfaz

El frontend combina:

- **Zona de consulta** — texto libre, ejemplos rápidos y parámetros (número de resultados, filtro de baja confianza).
- **Catálogo** — capas disponibles en la base de datos.
- **Resultados** — interpretación de la consulta, filtros, mapa OpenLayers y tabla.

![Zona de consulta](.images/search_zone.png)

En el mapa, las detecciones aparecen como geometrías coloreadas según confianza; puedes cambiar entre capas base (calles / satélite) y filtrar por clase, confianza o similitud CLIP.

![Mapa con detecciones y filtros](.images/ares_map_interface.png)

## Cómo lanzar una búsqueda

1. Comprueba que el indicador muestre **API activa** (puedes forzar un rechequeo desde la cabecera).
2. Escribe la consulta en el campo de texto, o elige un **ejemplo** (chips).
3. (Opcional) Ajusta el **número de resultados** y el interruptor para filtrar resultados de baja confianza.
4. Pulsa **Buscar** (o Enter).

La respuesta es un GeoJSON `FeatureCollection`. El frontend pinta las features en el mapa, rellena la tabla y permite abrir la interpretación (*Más info*).

### Ejemplos útiles

| Consulta | Qué suele hacer |
|----------|-----------------|
| `piscinas` | Búsqueda por clase (fast-path sin LLM si el catálogo encaja) |
| `coches` / `cars` | Clase de vehículo (ES/EN) |
| `coches rojos` | Clase + atributo de color vía CLIP |
| `coches cerca de rotonda` | Búsqueda espacial: *target* cerca de *reference* |
| `cars near buildings` | Igual en inglés |

## Tipos de consulta

### Por clase o atributos

Frases que nombran un tipo de objeto (y opcionalmente color u otro atributo). La API filtra por clase YOLO cuando puede y ordena por similitud CLIP del texto embebido (solo *target* + atributos, no la frase espacial completa).

### Espaciales («cerca de»)

Distinguen **objetivo** (*target*) y **referencia** (*reference*), con relación `near` y un radio en metros (default de la API: 50 m; máximo 500). Ejemplo: «coches cerca de rotonda».

En resultados espaciales verás:

- Distancia a la referencia (`distance_to_reference_m`) cuando la tabla la expone.
- Features de referencia en el mapa (capa aparte).
- En la interpretación: intención `search_spatial`, distancia usada y resumen en lenguaje natural.

Si no hay coincidencias, prueba a reformular la consulta o a llamar a la API con un `spatial_distance_m` mayor (p. ej. desde el visor de testing o `POST /search`).

### Cómo se interpreta (orden interno)

No hace falta conocerlo para usar el frontend, pero ayuda a leer el panel de interpretación:

1. **Overrides** explícitos en la API (`target`, `reference`, …) → sin Ollama.
2. **Parser determinista** si la frase es inequívoca respecto al catálogo → sin Ollama (`llm_ms=0`).
3. **Ollama** (+ fallback de catálogo) si hace falta.

La fuente aparece en `metadata.interpretation.source` (`override` | `parser` | `cache` | `llm`).

## Lectura de resultados

### Panel de interpretación

Tras cada búsqueda, *Más info* resume cómo se entendió la consulta: intención, clase/atributos del *target*, referencia espacial si aplica, texto embebido por CLIP y resumen en español/inglés. Úsalo para comprobar que la API no malinterpretó la frase antes de confiar en el mapa.

### Mapa

- Zoom / pan sobre las detecciones.
- Capas del catálogo y leyenda de confianza (alta / media / baja).
- En consultas espaciales, referencias dibujadas aparte del *target*.

### Tabla

Columnas típicas: ID, clase, confianza y capa. Puedes seleccionar filas y descargar el GeoJSON de resultados.

![Lista de resultados](.images/lista_busquedas.png)

### Filtros en cliente

Sin relanzar la búsqueda puedes restringir el conjunto mostrado en el mapa (capas, clases YOLO, confianza, similitud, etc.).

## Visor de testing (`api_webviewer`)

Para depurar la API a mano (opciones `top_k` / `per_layer_limit` / `min_confidence` / distancia, tabla ampliada, JSON crudo e historial local de las últimas 5 consultas), usa [`api_webviewer/`](../api_webviewer/). Es una herramienta secundaria, no el frontend de producto. Arranque y dependencias: [`api_webviewer/README.md`](../api_webviewer/README.md).

## Uso directo de la API

Si no usas el frontend:

```http
POST /search
Content-Type: application/json

{
  "query": "coches cerca de rotonda",
  "top_k": 50,
  "spatial_distance_m": 30
}
```

Overrides explícitos (tienen prioridad sobre el LLM):

```json
{
  "query": "vehículos junto a rotondas",
  "target": "vehicle",
  "reference": "roundabout",
  "spatial_relation": "near",
  "spatial_distance_m": 50
}
```

Otros endpoints útiles: `GET /health`, `GET /catalog`, `GET`/`DELETE /cache/llm`. Detalle completo en la [API reference](../api/README.md) y en `http://127.0.0.1:8000/docs` con el servidor en marcha.

## Problemas frecuentes

| Síntoma | Qué revisar |
|---------|-------------|
| API inactiva / error de conexión | Que `uvicorn` esté en marcha y `NEXT_PUBLIC_API_URL` apunte al puerto correcto (CORS). |
| 0 resultados en clase | Catálogo y tablas cargados; nombre de clase en catálogo; filtro de baja confianza demasiado agresivo. |
| 0 resultados espaciales | Aumentar `spatial_distance_m` vía API o `api_webviewer`; comprobar que existen *target* y *reference* en la zona. |
| 503 / LLM no disponible | Arrancar Ollama y tirar el modelo; o reformular a una consulta inequívoca (parser). |
| Mapa vacío pero tabla con filas | Filtros del cliente demasiado restrictivos. |
| Primera búsqueda lenta | Carga en frío de CLIP en el arranque de la API. |

## Más documentación

- [README del repositorio](../README.md)
- [Preparación de datos](preparacion-de-datos.md) — crear un dataset de prueba desde una ortofoto
- [API (`api/README.md`)](../api/README.md)
- [Pipeline offline (`tools/README.md`)](../tools/README.md)
- [Memoria técnica](memtech/)
