# Conclusiones

## Qué se ha conseguido

ARES demuestra, de extremo a extremo, que es viable **consultar en lenguaje natural un índice de detecciones aéreas** sin obligar al usuario a construir filtros GIS ni SQL. Sobre ortofotos de prueba en Madrid se ha materializado una cadena completa:

1. **Indexación offline** — tiles XYZ, detección multi-modelo YOLO, embeddings CLIP imagen y carga en PostgreSQL (PostGIS + pgvector).
2. **Servicio de búsqueda** — API FastAPI con Clean Architecture, interpretación override → parser → Ollama, búsqueda híbrida (clase + ranking CLIP) y espacial (`near` / `ST_DWithin`).
3. **Interacción** — visor de producto (Next.js + OpenLayers) con mapa, tabla, filtros e interpretación auditable; visor secundario de testing de la API.
4. **Operabilidad local** — stack open source ejecutable en CPU, con LLM pequeño vía Ollama y fast-path (`llm_ms=0`) cuando la consulta es inequívoca.

Las aportaciones prácticas del trabajo, contrastadas en los capítulos de solución, implementación y resultados, son:

- Un **contrato GeoJSON** estable (`metadata.interpretation`, *timings*, referencias espaciales) usable por más de un cliente.
- La **separación offline/online**, que deja el coste de visión fuera del camino interactivo.
- La **descomposición semántica/espacial** (CLIP solo sobre *target* + atributos; geometría en PostGIS), que evita contaminar el ranking con la frase espacial completa.
- Evidencia **cualitativa** de consultas de clase (`piscinas`), atributo visual (`coches rojos`), dominio energético (`paneles solares`) y proximidad (`coches cerca de rotondas`).

En conjunto, el sistema cumple el objetivo planteado en la introducción: reducir la barrera de acceso a detecciones georreferenciadas mediante frases naturales en español e inglés, con despliegue controlable por el operador del dato.

## Limitaciones actuales

Las limitaciones no invalidan el enfoque; delimitan el perfil de uso:

| Ámbito | Limitación |
|--------|------------|
| Cobertura | Solo existe en el índice lo que YOLO ha detectado y el catálogo reconoce; clases fuera de los especialistas quedan invisibles. |
| Calidad del detector | Errores de detección (falsos positivos/negativos, umbrales) se propagan a toda búsqueda posterior. |
| Semántica CLIP | El ranking por color u otros atributos es aproximado; no hay ground truth tabular de apariencia. |
| Espacial | Operativa la relación `near`; `inside` / `within` están preparadas en esquema pero no implementadas. |
| Lenguaje | El parser cubre frases inequívocas; el LLM puede fallar o caer en *fallback* de catálogo en paráfrasis difíciles. |
| Evaluación | Validación cualitativa sobre AOI de prueba; sin banco etiquetado precision/recall por tipo de consulta. |
| Escala | El lab local no caracteriza aún rendimiento a ciudad completa ni concurrencia de producción. |
| Producto GIS | No sustituye edición vectorial, geoprocesos avanzados ni publicación OGC institucional. |

## Trabajo futuro

Líneas naturales de continuación, ordenadas por impacto sobre el producto:

### Capacidad de consulta

1. **Relaciones espaciales adicionales** — implementar `inside` / `within` (contención PostGIS) reutilizando el schema ya preparado en `StructuredQuery`.
2. **Filtro por `bbox` / AOI** — restringir candidatos a una ventana cartográfica antes o después del ranking semántico.
3. **Más atributos y sinónimos** — ampliar catálogos de color/material y cobertura lingüística del parser sin pasar siempre por el LLM.
4. **Overrides ricos desde el visor** — exponer en UI distancia, *target* y *reference* tipados (hoy más naturales vía API / testing viewer).

### Calidad y evaluación

5. **Banco de evaluación cuantitativa** — conjunto de consultas etiquetadas (clase, atributo, espacial) con métricas precision@k / recall y tasas de acierto de interpretación (`source` parser vs llm).
6. **Calibración CLIP / umbrales** — estudio de bandas de similitud por clase y políticas de filtrado por defecto en el frontend.
7. **Normalización de vocabulario YOLO** — unificar alias (`swimming pool` vs `swimming_pool`) en indexado o en capa de catálogo.

### Rendimiento y operación

8. **Calentamiento y carga** — precarga de CLIP/Ollama; medición formal de `timings` bajo carga; afinar `LLM_CACHE_MAXSIZE` según el patrón real de consultas (la LRU ya está en producción local).
9. **Aceleración opcional** — GPU/CUDA y backend ONNX de CLIP como perfil de despliegue, manteniendo CPU como camino feliz documentado.
10. **Indexación incremental** — pipelines que actualicen solo tiles nuevos o modelos añadidos, con versionado de capa en catálogo.

### Experiencia de uso e integración

11. **UX del visor** — historial de búsquedas en el frontend de producto, comparación de interpretaciones, descarga filtrada, mejor legenda de referencias espaciales.
12. **Integración GIS** — publicación WFS/OGC API Features o plugins QGIS consumidores del mismo GeoJSON.
13. **Gobernanza del dato** — trazabilidad de campaña de indexado (modelo, fecha, AOI) en `metadata` de capa para auditoría.

Estas líneas no requieren replantear la arquitectura: el esqueleto (índice materializado + interpretación tipada + híbrida/espacial + contrato GeoJSON) admite evolucionar por **puertos y catálogo** sin reescribir el caso de uso central.

## Cierre

ARES deja un sistema **operable y documentado** para explorar detecciones aéreas con lenguaje natural, en un despliegue local y explicable. El valor inmediato es de **demostración técnica y base de producto**; el valor a medio plazo depende de cerrar evaluación cuantitativa, ampliar relaciones espaciales y endurecer el camino a producción. Con esas piezas, el mismo diseño puede pasar de memoria técnica a herramienta de trabajo sobre ortofotos reales a escala operativa.
