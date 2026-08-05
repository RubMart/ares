# Reverse proxy nginx (ARES)

Configuración de ejemplo para exponer el stack ARES detrás de un único punto de entrada HTTP: frontend, API y ortofotos COG.

Se usa con [`docker-compose.v2.18.yml`](../../docker-compose.v2.18.yml) (servicio `nginx`). También puedes montar [`ares.conf`](ares.conf) en un nginx del host apuntando a los mismos upstreams.

## Rutas

| Prefijo | Destino | Notas |
|---------|---------|--------|
| `/` | `frontend:3000` | Visor Next.js |
| `/api/` | `api:8000` | Se elimina el prefijo: `/api/search` → `/search` |
| `/data/` | ficheros en `/var/www/data` | COGs con HTTP Range + CORS para el mapa |

Puerto publicado en el Compose v2.18: **`NGINX_PORT`** (default `7070` → contenedor `:80`). El 80 del host suele estar ocupado.

## Arranque con Compose v2.18

Desde la raíz del repo:

```powershell
copy .env.example .env
```

En `.env`, para acceso vía proxy:

```env
NEXT_PUBLIC_API_URL=http://localhost:7070/api
NGINX_PORT=7070
COG_DATA_PATH=./data
```

```powershell
docker compose -f docker-compose.v2.18.yml up -d --build
```

- Entrada: `http://localhost:7070/`
- API (OpenAPI): `http://localhost:7070/api/docs`
- COG de ejemplo: `http://localhost:7070/data/<fichero>.tif`

`NEXT_PUBLIC_API_URL` se embebe en el **build** del frontend. Si la cambias, reconstruye el servicio `frontend`.

## Ficheros

| Fichero | Uso |
|---------|-----|
| [`ares.conf`](ares.conf) | `server` montado como `/etc/nginx/conf.d/default.conf` en el contenedor `ares-nginx` |

Montajes del servicio `nginx` en el Compose:

- `./deploy/nginx/ares.conf` → `/etc/nginx/conf.d/default.conf` (solo lectura)
- `${COG_DATA_PATH:-./data}` → `/var/www/data` (solo lectura)

## COGs y catálogo

1. Coloca los GeoTIFF COG en el directorio de `COG_DATA_PATH` (p. ej. `./data`).
2. En `detecciones_catalogo.cog_url`, usa la URL pública del proxy, p. ej. `http://<host>:7070/data/<capa>.tif`.
3. nginx responde Range (`206`) y cabeceras CORS necesarias para OpenLayers / GeoTIFF.

Detalle: [`doc/cog-y-visor.md`](../../doc/cog-y-visor.md).

## HTTPS

`ares.conf` escucha en el puerto 80 sin `server_name`. Para producción con TLS:

- Terminar HTTPS en un proxy delante (recomendado si ya tienes certbot / balanceador), o
- Activar los bloques `listen 443 ssl` comentados en `ares.conf` y montar certificados en el contenedor.

Ajusta `NEXT_PUBLIC_API_URL` y las `cog_url` a `https://…` y reconstruye el frontend.

## Diferencias respecto al Compose principal

[`docker-compose.yml`](../../docker-compose.yml) no incluye nginx: frontend y API se publican en `3000` / `8000`. El fichero v2.18 añade el proxy y evita `depends_on: service_completed_successfully` (no disponible en Compose 2.18.x).
