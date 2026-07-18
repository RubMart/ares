# Resumen

**Palabras clave:** búsqueda semántica, teledetección, imágenes aéreas, YOLO, CLIP, PostGIS, lenguaje natural

## Qué problema resuelve ARES

Las imágenes aéreas de alta resolución constituyen una fuente cada vez más rica de información territorial: vehículos, edificaciones, infraestructuras hidráulicas, instalaciones energéticas y otros elementos del paisaje urbano o periurbano. No obstante, el acceso a dicho contenido permanece, en gran medida, mediado por entornos GIS, filtros categóricos predefinidos o consultas técnicas sobre la base de datos. Esta dependencia dificulta que un usuario sin expertise geoespacial formule preguntas naturales del tipo «¿dónde hay coches rojos?» o «¿qué paneles solares se hallan próximos a edificios?».

ARES (*AI Retrieval of Entities in Space*) se propone reducir esa barrera. El sistema transforma las detecciones de objetos en un índice semántico y espacial consultable en lenguaje natural, de forma que la exploración del contenido de la imagen no requiera dominio previo de herramientas GIS ni de interfaces rígidas basadas en filtros.

## Qué tecnologías utiliza

La solución integra visión por computador, representación multimodal, almacenamiento espacial-vectorial e interpretación lingüística:

- **YOLO**, para la detección de objetos sobre imágenes aéreas de alta resolución y la generación de entidades georreferenciadas con geometría y confianza asociadas.
- **CLIP**, para proyectar detecciones y texto de consulta en un espacio semántico compartido.
- **PostgreSQL**, junto con las extensiones **PostGIS** y **pgvector**, para la persistencia de geometrías, el cálculo de relaciones de proximidad y la indexación vectorial.
- Un **modelo de lenguaje** ejecutado localmente mediante **Ollama**, encargado de interpretar la consulta y estructurarla en intención, clases, atributos y, cuando procede, relaciones espaciales.
- **Python** y **FastAPI**, como soporte de la API REST de consulta.
- **OpenLayers**, como cliente cartográfico para la representación de resultados sobre mapa.

## Qué resultado obtiene el usuario

A partir de una consulta formulada en español o en inglés, el sistema interpreta la petición, recupera las detecciones pertinentes —mediante filtro de clase, similitud semántica y, en su caso, proximidad espacial— y entrega un GeoJSON apto para visualización cartográfica, acompañado de metadatos que explicitan la interpretación realizada.

El usuario puede consumir estos resultados tanto a través de la API como desde el visor web, donde se combinan mapa, tabla y detalle JSON, sin necesidad de construir manualmente filtros GIS.

## Principales aportaciones

1. **Pipeline extremo a extremo**, desde la imagen aérea hasta la entidad indexada: detección, embedding y almacenamiento espacial-vectorial.
2. **Búsqueda híbrida**, que combina un filtro categórico por clase YOLO con un ranking por similitud CLIP, coherente con los embeddings de imagen previamente generados.
3. **Consultas espaciales enriquecidas**, mediante la distinción entre *target*, *reference* y relación espacial (p. ej. «cerca de»), resuelta con operadores PostGIS.
4. **Capa de interacción**, constituida por una API REST y un visor cartográfico que hacen transparente la interpretación de la consulta y la presentación de los resultados.
