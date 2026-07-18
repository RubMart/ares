# Descripción de la solución

> Sección central de la memoria técnica.

## Arquitectura general

Flujo extremo a extremo:

```text
Imagen aérea de alta resolución
  ↓
Detección de objetos
  ↓
Generación de embeddings
  ↓
Base de datos vectorial (+ espacial)
  ↓
Consulta en lenguaje natural
  ↓
Resultados sobre mapa
```

<!-- A completar: diagrama y explicación de cada etapa del pipeline. -->

## Componentes

### Procesamiento de imágenes

<!-- Detección sobre teselas / imágenes aéreas de alta resolución y generación de entidades geométricas. -->

### Indexación semántica

<!-- Embeddings CLIP, almacenamiento vectorial y catálogo de capas. -->

### API de consulta

<!-- Interpretación NL → consulta estructurada → búsqueda híbrida/espacial → GeoJSON. -->

### Visor cartográfico

<!-- Interfaz web para lanzar consultas y visualizar resultados en mapa, tabla y JSON. -->

## Tecnologías empleadas

| Tecnología | Rol en ARES |
|------------|-------------|
| YOLO | Detección de objetos en imágenes aéreas de alta resolución |
| CLIP | Embeddings multimodales texto–imagen |
| PostgreSQL + PostGIS + pgvector | Geometrías, proximidad espacial e índice vectorial |
| OpenLayers | Visualización cartográfica en el cliente |
| Python / FastAPI | API REST de consulta |

<!-- A completar: justificación breve de cada elección tecnológica. -->
