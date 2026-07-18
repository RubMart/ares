# Implementación

> Decisiones de diseño e implementación relevantes.

## Detección de objetos

Cómo se generan las entidades a partir de imágenes aéreas de alta resolución (modelos YOLO, clases, geometrías, confianza).

<!-- A completar. -->

## Almacenamiento

Cómo se guardan geometrías y embeddings (esquema PostGIS, `vector(512)`, catálogo de capas, índices).

<!-- A completar. -->

## Búsqueda semántica

Cómo se transforma una consulta en lenguaje natural en resultados: análisis LLM, fallback de catálogo, filtro por clase, ranking CLIP y, en su caso, proximidad PostGIS (`target` / `reference` / relación).

<!-- A completar. -->

## Visualización

Cómo se representan los resultados sobre el mapa (GeoJSON, capas, metadatos de interpretación, tabla/JSON en el visor).

<!-- A completar. -->
