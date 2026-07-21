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
