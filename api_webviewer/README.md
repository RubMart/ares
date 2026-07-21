# API Web Viewer

Visor **estático de testing** para la API de ARES. Sirve para probar a mano `POST /search`, `GET /health`, `GET /catalog` y la caché LLM (`GET`/`DELETE /cache/llm`), viendo resultados en mapa, tabla y JSON crudo.

**No es el frontend de producto.** No tiene propósito público ni UX de usuario final: es una herramienta interna, simple, solo para desarrollo y depuración del contrato HTTP. El visor de producto está en [`../frontend/`](../frontend/).

Índice del monorepo: [`../README.md`](../README.md). Contrato de la API: [`../api/README.md`](../api/README.md).

## Qué incluye

- Formulario de búsqueda con ejemplos, opciones avanzadas (`top_k`, `per_layer_limit`, `min_confidence`, distancia espacial) y URL base de la API configurable
- Mapa OpenLayers (detecciones + referencias espaciales; capa COG opcional)
- Tabla ordenable, filtros en cliente, panel de interpretación / metadata
- Visor del GeoJSON de respuesta (copiar al portapapeles)
- Catálogo de capas y panel de caché LLM
- Historial local de las últimas 5 consultas (`localStorage`, clave `api_webviewer_search_history`)

## Requisitos

| Componente | Uso |
|------------|-----|
| Navegador moderno | Ejecuta el HTML/JS; no hay build ni Node |
| API ARES en marcha | Por defecto `http://localhost:8000` (CORS ya habilitado en la API) |
| Python 3 (opcional) | Solo para servir los ficheros estáticos (`python -m http.server`) |
| Red | Librerías del mapa desde CDN (jsDelivr); OSM como fondo del mapa |

No hay `package.json` ni `requirements.txt` en esta carpeta: **cero dependencias npm/pip** del propio visor.

### Dependencias en runtime (CDN)

Cargadas desde jsDelivr en `index.html`:

| Librería | Versión | Para qué |
|----------|---------|----------|
| [OpenLayers](https://openlayers.org/) | 9.2.4 | Mapa, capas vectoriales, GeoTIFF |
| [proj4](https://proj4js.org/) | 2.11.0 | Proyecciones (p. ej. EPSG:25830/25831) |
| [geotiff.js](https://geotiffjs.github.io/) | 2.1.3 | Lectura de ortofotos COG (capa opcional) |

Sin red al CDN el mapa no carga esas librerías. La API y PostgreSQL son requisitos del backend, no de este directorio.

## Estructura

```
api_webviewer/
├── index.html      # UI: búsqueda, catálogo, caché, mapa/tabla/JSON
├── css/
│   └── styles.css
└── js/
    ├── api.js      # Cliente fetch + historial en localStorage
    ├── map.js      # OpenLayers + GeoJSON + COG opcional
    └── app.js      # Orquestación UI
```

## Cómo ejecutarlo

1. Arranca la API (ver [`../api/README.md`](../api/README.md)):

```powershell
cd api
.\.venv\Scripts\Activate.ps1
uvicorn main:app --reload --app-dir .
```

2. En otra terminal, sirve esta carpeta:

```powershell
cd api_webviewer
python -m http.server 8080
```

3. Abre [http://localhost:8080](http://localhost:8080).

La URL base de la API se edita en la cabecera del visor (por defecto `http://localhost:8000`) y se guarda en `localStorage` (`api_webviewer_base_url`). También puedes cambiar el default en `js/api.js` si hace falta.

### Ortofoto COG (opcional)

El mapa usa OSM por defecto. Si quieres superponer un COG, sírvelo con soporte HTTP Range (p. ej. en el puerto 4040) y carga la URL desde la UI cuando el catálogo o la respuesta lo indiquen. No es necesario para probar búsquedas ni el GeoJSON.

## Uso rápido

1. **Comprobar conexión** → badge de health (API + BD + CLIP).
2. Escribe una consulta (`piscinas`, `coches cerca de rotonda`, …) o usa un chip de ejemplo → **Buscar**.
3. Revisa interpretación en el panel de metadata, features en mapa/tabla y el JSON crudo.
4. Ajusta filtros en cliente o parámetros avanzados y vuelve a buscar.

Para el flujo de producto (UX, i18n, chips espaciales, etc.) usa [`../frontend/`](../frontend/) ([README](../frontend/README.md)) y la [guía de uso](../doc/guia-de-uso.md).
