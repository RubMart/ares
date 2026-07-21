# Frontend (visor de producto)

Visor web de ARES: consulta en lenguaje natural, mapa OpenLayers, tabla de resultados e interpretación visible de cómo la API entendió la frase.

Stack: **Next.js 16** (App Router) + **React 19** + **OpenLayers** + **Tailwind CSS 4** + **i18next** (ES/EN). Habla con la API FastAPI vía `fetch` (`GET /health`, `GET /catalog`, `POST /search`).

Índice del monorepo: [`../README.md`](../README.md). Contrato HTTP: [`../api/README.md`](../api/README.md). Guía de uso (UX): [`../doc/guia-de-uso.md`](../doc/guia-de-uso.md).

> El visor estático [`../api_webviewer/`](../api_webviewer/) es solo para testing de la API (mapa + JSON crudo). Este directorio es la UI de producto.

## Qué incluye

- Panel de búsqueda: texto libre, chips de ejemplo, `top_k` (número de resultados) y filtro de baja confianza (`min_confidence` 0.7 / 0.0)
- Badge de estado de la API (`GET /health`, polling ~15 s)
- Catálogo de capas (`GET /catalog`) con control de visibilidad en el mapa
- Mapa OpenLayers: detecciones + capa de referencias espaciales; basemap calles / satélite
- Filtros en cliente: capa, clase YOLO, nivel de confianza, rango de similitud CLIP
- Tabla de resultados, descarga GeoJSON (todos / filtrados) e interpretación (`metadata.interpretation`)
- i18n ES/EN (preferencia en `localStorage`, clave `ares_lng`)

## Requisitos

| Componente | Uso |
|------------|-----|
| [Node.js](https://nodejs.org/) 20+ (LTS) | Runtime de Next.js |
| npm (o pnpm) | Instalar dependencias (`package-lock.json` / `pnpm-lock.yaml`) |
| API ARES en marcha | Por defecto `http://127.0.0.1:8000` (CORS habilitado en la API) |
| PostgreSQL + datos | Sin índice de detecciones no hay resultados útiles |
| Ollama (recomendado) | Consultas ambiguas; las inequívocas pueden ir por parser sin LLM |

### Dependencias principales (`package.json`)

| Grupo | Paquetes |
|-------|----------|
| App | `next`, `react`, `react-dom` |
| Mapa | `ol`, `proj4` |
| UI | `tailwindcss`, `@base-ui/react`, `lucide-react`, `class-variance-authority`, `clsx`, `tailwind-merge` |
| i18n | `i18next`, `react-i18next`, `i18next-browser-languagedetector` |

## Estructura

```
frontend/
├── app/                      # App Router (layout, page, estilos globales)
├── components/
│   ├── ares/                 # UI de producto (mapa, búsqueda, filtros, …)
│   └── ui/                   # Primitivos (button, dialog, slider)
├── hooks/                    # useApiStatus, useCatalog
├── lib/
│   ├── api/                  # Cliente HTTP, tipos, search / health / catalog
│   ├── geojson/              # Descarga de resultados
│   ├── i18n/                 # Config + locales es.json / en.json
│   ├── map/                  # Confianza, geometría, proyecciones
│   ├── search-limits.ts      # MAX_QUERY_LENGTH desde env
│   └── search-catalog.ts
├── public/                   # icon.svg y assets estáticos
├── .env.example              # Plantilla de variables públicas
├── next.config.mjs
└── package.json
```

## Variables de entorno

Copia la plantilla y edita si hace falta:

```powershell
cd frontend
copy .env.example .env.local
```

Linux/macOS: `cp .env.example .env.local`.

Next.js solo expone al navegador variables con prefijo `NEXT_PUBLIC_`. El fichero `.env.local` **no** se versiona (está en `.gitignore`).

| Variable | Default (`.env.example`) | Descripción |
|----------|--------------------------|-------------|
| `NEXT_PUBLIC_API_URL` | `http://127.0.0.1:8000` | Base URL de la API **sin** barra final. Obligatoria: sin ella el cliente lanza error. En Windows preferir `127.0.0.1` frente a `localhost` (evita IPv6 `::1` si uvicorn escucha solo en IPv4). |
| `NEXT_PUBLIC_MAX_QUERY_LENGTH` | `500` | Máximo de caracteres en el campo de consulta. Mantener alineado con `MAX_QUERY_LENGTH` de la API. |

Tras cambiar variables `NEXT_PUBLIC_*`, reinicia `npm run dev` (se inyectan en build/arranque).

## Instalación y ejecución

Con la **API ya en marcha** (ver [`../api/README.md`](../api/README.md)):

```powershell
cd frontend
copy .env.example .env.local
npm install
npm run dev
```

Abre [http://127.0.0.1:3000](http://127.0.0.1:3000).

El script `dev` fija host `127.0.0.1` y puerto `3000` (webpack). `next.config.mjs` permite orígenes de desarrollo `127.0.0.1` y `localhost` (HMR en Next 16).

### Scripts npm

| Script | Qué hace |
|--------|----------|
| `npm run dev` | Desarrollo en `http://127.0.0.1:3000` |
| `npm run build` | Build de producción |
| `npm run start` | Sirve el build (mismo host/puerto) |
| `npm run preview` | `build` + `start` |
| `npm run lint` | ESLint |

Con pnpm: `pnpm install` y los mismos scripts (`pnpm dev`, …).

## Uso rápido

1. Comprueba el badge de API (online / degraded / offline); puedes forzar un rechequeo.
2. Escribe una consulta (`piscinas`, `coches rojos`, `coches cerca de rotonda`, …) o usa un chip de ejemplo → **Buscar**.
3. Revisa mapa, tabla e interpretación (*Más info*). En espaciales verás también la capa de referencias.
4. Ajusta filtros en cliente o parámetros del panel y vuelve a buscar.

Detalle de UX, tipos de consulta e interpretación: [`../doc/guia-de-uso.md`](../doc/guia-de-uso.md).

### Parámetros que envía el visor a `POST /search`

| UI | Campo API | Notas |
|----|-----------|--------|
| Texto de consulta | `query` | Truncado a `NEXT_PUBLIC_MAX_QUERY_LENGTH` |
| Número de resultados | `top_k` | Default UI: 50 |
| Filtrar baja confianza | `min_confidence` | `0.7` si activo; si no, `0.0` |

La interpretación espacial (`target` / `reference` / `near`) la resuelve la API a partir del texto; el frontend no envía overrides HTTP salvo lo anterior. Timeout de búsqueda en cliente: 60 s (`SEARCH_TIMEOUT_MS`); el resto de llamadas HTTP usan ~12 s.

## Relación con el resto del stack

```
Ortofoto → tools/ → PostgreSQL  →  api/ (FastAPI)  →  frontend/ (este visor)
```

1. Datos: [`../db/README.md`](../db/README.md) y [`../doc/preparacion-de-datos.md`](../doc/preparacion-de-datos.md).
2. API: [`../api/README.md`](../api/README.md).
3. Testing crudo de endpoints: [`../api_webviewer/README.md`](../api_webviewer/README.md).
