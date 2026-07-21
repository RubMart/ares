# Introducción

## Contexto y motivación

Las ortofotos y las imágenes aéreas de alta resolución se han consolidado como fuente primaria de información territorial: inventarios de vehículos, seguimiento de infraestructuras, localización de instalaciones energéticas o hidráulicas, y exploración del tejido urbano. En paralelo, la visión por computador permite extraer de esas imágenes **detecciones georreferenciadas** —objetos con geometría, clase y confianza— a una escala que ya no es manejable mediante inspección visual exhaustiva.

El cuello de botella, sin embargo, se ha desplazado del reconocimiento al **acceso**. Una vez indexadas las detecciones, el usuario típico sigue enfrentándose a interfaces GIS orientadas a capas y atributos, a consultas SQL/espaciales, o a catálogos de clases rígidos. Formular una pregunta natural del tipo «coches rojos cerca de una rotonda» exige, en la práctica, traducir la intención a filtros, buffers y joins que no son accesibles sin expertise geoespacial.

ARES (*AI Retrieval of Entities in Space*) nace de esa fricción: **convertir un índice de detecciones ya calculadas en un recurso consultable en lenguaje natural**, combinando semántica multimodal (CLIP), filtro categórico (clases YOLO), proximidad espacial (PostGIS) e interpretación lingüística local (parser determinista + Ollama), y exponiendo el resultado como GeoJSON sobre un visor cartográfico.

## Problema técnico

El problema que aborda este trabajo no es «detectar objetos en imagen aérea» de forma aislada —tarea ya cubierta por detectores como YOLO—, sino **recuperar entidades espaciales a partir de una consulta en lenguaje natural** sobre un corpus de detecciones previamente indexadas. Eso implica resolver, de forma conjunta:

1. **Ambigüedad lingüística**: la misma intención puede expresarse en español o inglés, con sinónimos, atributos (p. ej. color) y relaciones espaciales («cerca de»).
2. **Heterogeneidad semántica**: el catálogo YOLO es discreto (clases fijas), mientras que el lenguaje del usuario es abierto; hace falta un puente entre ambos.
3. **Componente espacial**: muchas consultas no piden solo «qué» sino «dónde respecto a qué» (*target* vs *reference*).
4. **Explicabilidad**: el usuario debe poder validar *cómo* se interpretó la frase, no solo consumir un listado opaco de features.
5. **Operabilidad local**: en muchos escenarios las ortofotos o las detecciones no pueden salir del entorno; la solución debe poder ejecutarse sin depender de APIs cloud de visión o de LLM externos.

## Objetivo general

Diseñar e implementar un sistema extremo a extremo que permita **buscar, en lenguaje natural (español e inglés), elementos detectados en imágenes aéreas de alta resolución**, recuperando entidades georreferenciadas mediante búsqueda híbrida (clase + similitud CLIP) y, cuando proceda, proximidad espacial, y presentándolas de forma comprensible en mapa y tabla.

## Objetivos específicos

1. Definir un **pipeline offline** de detección (YOLO), embedding (CLIP) e indexación en PostgreSQL (PostGIS + pgvector).
2. Exponer una **API REST** que interprete la consulta, embeba el texto pertinente y ejecute búsqueda híbrida o espacial.
3. Minimizar la dependencia del LLM mediante un **fast-path** (overrides HTTP + parser determinista) cuando la consulta es inequívoca respecto al catálogo.
4. Soportar consultas espaciales enriquecidas con distinción *target* / *reference* y relación de proximidad (`near`), resuelta con `ST_DWithin`.
5. Ofrecer un **visor de producto** (mapa + tabla + interpretación visible) y un contrato GeoJSON estable para integración.
6. Mantener un despliegue **local, reproducible y operable en CPU**, con stack open source.

## Comparación con otras soluciones

A continuación se sitúa ARES frente a enfoques habituales para explorar o consultar contenido derivado de imagen aérea. No se pretende un *benchmark* cuantitativo, sino un marco de decisión técnico.

| Enfoque | Cómo opera | Fortalezas | Debilidades frente al problema de ARES |
|---------|------------|------------|----------------------------------------|
| **Visor / GIS clásico** (QGIS, ArcGIS, capas WMS/WFS) | Filtros por capa, atributo, selección espacial manual | Madurez, precisión cartográfica, ecosistema amplio | Requiere expertise GIS; no interpreta lenguaje natural; la semántica «visual» (p. ej. color) no está en el atributo |
| **Catálogo + filtros HTTP** (API de features por `class_id`) | Consultas tipadas, parámetros fijos | Predecible, fácil de cachear, bajo coste | No admite frases abiertas ni atributos no tabulados; el usuario debe conocer el esquema |
| **Búsqueda solo vectorial** (CLIP / embedding puro sobre tiles o crops) | Similitud texto–imagen sin filtro de clase | Flexible ante vocabulario abierto | Ruido y falsos positivos; sin control espacial explícito; difícil acotar por tipo de objeto |
| **APIs cloud de visión + LLM** (p. ej. visión gestionada + GPT) | Detección/descripción bajo demanda en la nube | Potencia de modelos grandes, poco *setup* inicial | Coste recurrente, latencia de red, dependencia de proveedor, restricciones de privacidad sobre ortofotos |
| **NL2SQL / geo-QA genérico** | LLM que genera SQL o WKT a partir del texto | Muy expresivo en teoría | Frágil sin *grounding* en catálogo; riesgo de SQL incorrecto; poca trazabilidad si no se diseña la interpretación |
| **ARES (esta solución)** | Índice offline YOLO+CLIP; interpretación local; híbrido clase+CLIP+PostGIS; GeoJSON + visor | Ver sección siguiente | Ver limitaciones |

En síntesis: los GIS y las APIs tipadas resuelven bien el *dónde* cuando el *qué* ya está estructurado; las búsquedas solo embedding resuelven el *qué* semántico pero debilitan el control; las soluciones cloud externalizan el coste operativo y de privacidad. ARES se sitúa en el **punto intermedio operativo**: detecciones estructuradas + semántica multimodal + espacio + lenguaje natural, con ejecución local.

## Ventajas de la solución propuesta

1. **Despliegue local y soberanía del dato.** PostgreSQL, CLIP y Ollama viven en la infraestructura del operador. Las ortofotos y el índice no tienen que enviarse a un proveedor externo de visión o de LLM.
2. **Operación en CPU.** Detección, embeddings, interpretación y API pueden ejecutarse sin GPU. La aceleración hardware es opcional, no un requisito de entrada; encaja en portátiles y servidores modestos.
3. **Búsqueda híbrida, no un único mecanismo.** El filtro por clase YOLO acota el universo de candidatos; CLIP ordena por similitud con la descripción textual (incluidos atributos como el color); PostGIS aporta la dimensión de proximidad. Cada capa compensa debilidades de las otras.
4. **LLM solo cuando aporta valor.** Overrides HTTP y parser determinista resuelven consultas inequívocas (`piscinas`, `coches cerca de rotonda`) sin llamar a Ollama (`llm_ms=0`). Se reduce latencia, variabilidad y dependencia del modelo.
5. **Modelo de lenguaje pequeño y asequible.** El default (`llama3.2:3b` vía Ollama) cabe en hardware corriente; no exige un modelo frontier ni suscripción.
6. **Consultas espaciales con semántica explícita.** La distinción *target* / *reference* / relación `near` evita embeber la frase espacial completa en CLIP (que distorsionaría el ranking) y delega la geometría a PostGIS.
7. **Interpretación visible y auditable.** La respuesta incluye `metadata.interpretation` (fuente `override` | `parser` | `llm`, intención, distancia, resumen). El usuario puede contrastar lo entendido con lo pedido.
8. **Stack abierto y contrato estándar.** Pipeline (`tools/`), API (FastAPI) y frontend (Next.js + OpenLayers) son open source; la salida GeoJSON facilita integración con otros clientes cartográficos.
9. **Separación offline / online.** El coste pesado de detección y embedding se asume una vez (o por lote); la consulta interactiva trabaja sobre un índice ya materializado.

## Desventajas y *trade-offs*

Toda decisión de diseño implica costes. Los más relevantes en ARES son:

| *Trade-off* | Implicación práctica |
|-------------|----------------------|
| **Calidad acotada al detector y al catálogo** | Solo se recupera lo que YOLO ha detectado y lo que el catálogo reconoce. Objetos fuera de clase o mal detectados son invisibles a la búsqueda. |
| **Semántica CLIP no es ground truth** | El ranking por similitud es aproximado; atributos como el color dependen de la calidad del crop y del embedding, no de un atributo tabulado verificado. |
| **Relación espacial limitada** | En el estado actual se implementa de forma operativa la proximidad (`near` / `ST_DWithin`). Relaciones del tipo *inside* / *within* están preparadas a nivel de esquema pero no implementadas. |
| **Cobertura lingüística imperfecta** | El parser determinista cubre frases inequívocas; el LLM cubre el resto con riesgo de interpretación errónea o de *fallback* de catálogo. |
| **Coste de indexación previo** | Antes de consultar hay que ejecutar el pipeline offline (tiles, detección, embeddings, carga SQL). No es búsqueda *ad hoc* sobre la ortofoto en crudo en tiempo de petición. |
| **Escala y evaluación** | El sistema está validado de forma cualitativa sobre datasets de prueba; no incluye aún un banco de evaluación cuantitativa (precision/recall por tipo de consulta). La caché LRU de interpretaciones reduce repeticiones del LLM, pero el dimensionado bajo carga formal queda abierto. |
| **No sustituye un GIS completo** | Edición de capas, análisis multicriterio avanzado, simbología cartográfica profesional o publicación OGC completa quedan fuera de alcance. |

Estas limitaciones no invalidan el enfoque; delimitan el **perfil de uso** para el que ARES está pensado: exploración semántico-espacial de un índice de detecciones, con bajo *friction* para el usuario y control local del despliegue.

## Alcance

### Qué hace el sistema

- **Detección offline** de objetos sobre teselas derivadas de ortofotos de alta resolución, mediante modelos YOLO, generando entidades con geometría, clase y confianza.
- **Generación de embeddings CLIP** (dimensión 512) asociados a cada detección, y miniaturas para apoyo visual.
- **Indexación** en PostgreSQL con PostGIS (geometrías, proximidad) y pgvector (similitud), organizada por catálogo de capas.
- **Interpretación de consultas** en español e inglés: overrides HTTP, parser determinista o Ollama (con caché LRU de interpretaciones), con *fallback* a catálogo cuando procede.
- **Búsqueda híbrida** (filtro de clase + ranking CLIP) y **búsqueda espacial** (*target* cerca de *reference* con radio configurable).
- **API REST** que devuelve GeoJSON (`FeatureCollection`) con metadatos de interpretación y, en consultas espaciales, distancia a la referencia y features de referencia.
- **Visor de producto** (mapa OpenLayers, tabla, filtros, chips espaciales, panel de interpretación) y un visor secundario de testing de la API.

### Qué no hace el sistema

- **No genera ni adquiere** las imágenes de entrada; parte de ortofotos / COGs ya disponibles.
- **No es un GIS completo**: no sustituye edición vectorial, geoprocesos complejos ni flujos de publicación cartográfica institucional.
- **No sustituye la fotointerpretación experta** ni garantiza exactitud legal o catastral de las detecciones.
- **No detecta en tiempo real** sobre el mapa durante la consulta; opera sobre un índice previamente materializado.
- **No implementa aún** relaciones espaciales de contención (`inside` / `within`) ni filtro por `bbox` como fase adicional de producto.
- **No depende** (ni pretende depender) de APIs cloud de visión o de LLM como camino feliz; el diseño prioriza el *stack* local.

## Metodología de trabajo (visión general)

El desarrollo se ha articulado en capas desacopladas, de forma que cada una pueda evolucionar sin romper el contrato de las demás:

1. **Pipeline offline** (`tools/`): detección → embedding → thumbnails → carga a PostgreSQL.
2. **Dominio y aplicación de búsqueda** (`api/`): Clean Architecture; caso de uso `SearchDetections` con orden fijo override → parser → (caché LRU \| LLM).
3. **Infraestructura**: repositorio PostGIS/pgvector, analizador Ollama, CLIP text encoder, serialización GeoJSON.
4. **Presentación**: frontend de producto y, de forma secundaria, visor estático de pruebas de la API.
5. **Documentación y decisiones**: planes de diseño, guías de uso y preparación de datos, y esta memoria técnica.

El detalle de arquitectura, implementación y resultados se desarrolla en los capítulos siguientes.

## Estructura de la memoria

| Capítulo | Contenido |
|----------|-----------|
| 02 · Resumen | Problema, tecnologías, resultado para el usuario y aportaciones |
| 03 · Introducción | Contexto, objetivos, comparación, ventajas/desventajas y alcance *(este capítulo)* |
| 04 · Descripción de la solución | Arquitectura, componentes y justificación tecnológica |
| 05 · Implementación | Arquitectura software, DI, caso de uso, adaptadores, frontend y tests |
| 06 · Resultados | Ejemplos, capturas y comportamiento observado |
| 07 · Conclusiones | Logros, limitaciones y trabajo futuro |
| 08 · Referencias | Documentación, software y literatura relevante |
