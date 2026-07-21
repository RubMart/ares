# Referencias

Documentación oficial, paquetes y literatura que sustentan el diseño e implementación de ARES. Las URLs se verificaron como punto de acceso habitual a cada recurso; las versiones concretas de dependencias figuran en `api/requirements.txt` y `tools/requirements.txt`.

---

## Documentación técnica y software

### Detección y visión

1. Ultralytics. *YOLO Docs* (YOLOv8 / YOLO11, OBB, CLI). Disponible en: https://docs.ultralytics.com/
2. Jocher, G. et al. Ultralytics YOLO — repositorio y modelos. GitHub. https://github.com/ultralytics/ultralytics
3. Xia, G.-S. et al. *DOTA: A Large-Scale Dataset for Object Detection in Aerial Images*. CVPR Workshops / dataset DOTA (cajas orientadas en teledetección). https://captain-whu.github.io/DOTA/
4. Zhu, P. et al. *VisDrone* — detección de objetos en imágenes de dron (base de modelos tipo VisDrone-YOLO usados en el stack). https://github.com/VisDrone/VisDrone-Dataset

### Representación multimodal (CLIP)

5. Radford, A. et al. *Learning Transferable Visual Models From Natural Language Supervision* (CLIP). ICML 2021. https://arxiv.org/abs/2103.00020
6. OpenAI / Hugging Face. Modelo `openai/clip-vit-base-patch32`. https://huggingface.co/openai/clip-vit-base-patch32
7. Hugging Face. Biblioteca *Transformers* (carga e inferencia CLIP). https://huggingface.co/docs/transformers

### Base de datos espacial y vectorial

8. PostgreSQL Global Development Group. *PostgreSQL Documentation*. https://www.postgresql.org/docs/
9. PostGIS Project. *PostGIS Manual* (`ST_DWithin`, `ST_Distance`, GeoJSON, índices GIST). https://postgis.net/documentation/
10. pgvector. Extensión de similitud vectorial para PostgreSQL (operador `<=>`, HNSW, `vector_cosine_ops`). https://github.com/pgvector/pgvector
11. GeoAlchemy2. ORM espacial sobre SQLAlchemy. https://geoalchemy-2.readthedocs.io/

### API, LLM local y frontend

12. FastAPI. *Documentation* (routing, Depends, lifespan, OpenAPI). https://fastapi.tiangolo.com/
13. Encode / Pydantic. *Pydantic v2*. https://docs.pydantic.dev/
14. SQLAlchemy. *asyncio* + asyncpg. https://docs.sqlalchemy.org/
15. Ollama. Ejecución local de LLMs (`llama3.2` y familia). https://ollama.com/ / https://github.com/ollama/ollama
16. LangChain. Integración *langchain-ollama* (structured output). https://python.langchain.com/
17. Meta AI. *Llama 3.2* — tarjetas de modelo y tamaños (p. ej. 3B). https://www.llama.com/
18. Next.js. *Documentation*. https://nextjs.org/docs
19. OpenLayers. *API documentation* (GeoJSON, View, capas vectoriales). https://openlayers.org/en/latest/apidoc/
20. GDAL/OGR. *gdal2tiles*, COG y utilidades raster. https://gdal.org/

### Arquitectura y buenas prácticas

21. Martin, R. C. *Clean Architecture: A Craftsman’s Guide to Software Structure and Design*. Prentice Hall, 2017. (Dependencias hacia el dominio; puertos y adaptadores.)
22. Fowler, M. *Patterns of Enterprise Application Architecture*. Addison-Wesley, 2002. (Repository, capas de aplicación.)

---

## Artículos y trabajos relacionados

### Detección en teledetección e imagen aérea

23. Cheng, G. & Han, J. *A survey on object detection in optical remote sensing images*. ISPRS Journal of Photogrammetry and Remote Sensing, 2016. https://doi.org/10.1016/j.isprsjprs.2016.03.014
24. Ding, J. et al. *Object Detection in Aerial Images: A Large-Scale Benchmark and Challenges*. IEEE TPAMI (línea DOTA / detección aérea). https://arxiv.org/abs/2102.12219

### CLIP, recuperación multimodal y búsqueda semántica

25. Jia, C. et al. *Scaling Up Visual and Vision-Language Representation Learning With Noisy Text Supervision* (ALIGN). ICML 2021. https://arxiv.org/abs/2102.05918
26. Li, J. et al. *BLIP: Bootstrapping Language-Image Pre-training for Unified Vision-Language Understanding and Generation*. ICML 2022. https://arxiv.org/abs/2201.12086  
   (Contexto de VLM posteriores a CLIP; ARES se limita a CLIP ViT-B/32 por coste y alineación offline/online.)

### Lenguaje natural y datos geoespaciales (NL2GIS / GeoQA)

27. Mai, G. et al. *Towards a foundation model for geospatial artificial intelligence (GeoAI)*. Actas y perspectivas GeoAI; útil como marco del cruce NLP–SIG. https://arxiv.org/abs/2304.06793
28. Literature de *natural language interfaces to GIS* / text-to-SQL espacial (p. ej. GeoQuery históricos y trabajos NL2SPARQL/NL2SQL geo). Se citan como **contraste**: ARES no genera SQL libre, sino un `StructuredQuery` acotado a catálogo YOLO + operadores PostGIS fijos.

### Sistemas híbridos vectoriales

29. Pan, J. J. et al. / literatura de *hybrid search* (filtro metadatos + ranking vectorial) en motores tipo pgvector, Elasticsearch kNN, etc. El patrón «filtro duro + similitud coseno» de ARES se alinea con esta práctica de recuperación, aplicada aquí a detecciones georreferenciadas.

---

## Datos y contexto cartográfico de las pruebas

30. **Ortofoto de prueba (fuente primaria del laboratorio ARES).** Ayuntamiento de Madrid — Subdirección General de Innovación e Información Urbana. *Ortofoto actualizada* (ortofotografía verdadera, GSD **2,5 cm**), vuelo fotogramétrico cenital y oblicuo de julio de 2024 sobre la zona urbana de la ciudad. Metadatos y acceso: Geoportal del Ayuntamiento de Madrid — https://geoportal.madrid.es/IDEAM_WBGEOPORTAL/dataset.iam?id=555821cd-9c3f-4043-87ed-2f3c002c2f22 ; portal de datos abiertos — https://datos.madrid.es/dataset/300740-0-ortofoto-cubierta-mosaico

   **Disclaimer / condiciones de uso de los datos de prueba.** Las capturas, índices (`madrid_*_detections`) y ejemplos de esta memoria se elaboraron a partir de **recortes (AOI)** de dicha ortofoto municipal, exclusivamente con fines de **demostración técnica y evaluación del TFM**. No constituyen un producto cartográfico oficial del Ayuntamiento de Madrid ni una publicación autorizada del mosaico completo. La autoría y los derechos de la ortofoto corresponden al Ayuntamiento de Madrid; cualquier reutilización del dato original debe respetar la licencia y condiciones publicadas en el portal municipal (p. ej. **CC BY 4.0** en el conjunto de datos abiertos, con atribución al Ayuntamiento de Madrid). ARES no redistribuye los rasters originales ni los pesos/datasets crudos en el repositorio.

31. Especificación *Cloud Optimized GeoTIFF* (COG). https://www.cogeo.org/

---

## Referencias internas del proyecto

32. Repositorio ARES — `README.md`, `AGENTS.md`, `api/README.md`, `tools/README.md`, `doc/preparacion-de-datos.md`, `doc/guia-de-uso.md`.
33. Planes de diseño en `.cursor/plans/` (búsqueda semántica, consulta espacial enriquecida, fast-path sin LLM, pipeline YOLO/CLIP/SQL, frontend).

---

## Nota bibliográfica

Las entradas [1]–[20] y [31]–[33] son las **fuentes de implementación** directas del sistema. La entrada [30] documenta la **fuente de la ortofoto de prueba** (Ayuntamiento de Madrid, 2024, 2,5 cm) y el disclaimer de uso. Las [23]–[29] sitúan ARES en el estado del arte (detección aérea, VLM, GeoAI / NL–GIS) sin pretender una revisión exhaustiva. Donde un trabajo se menciona como contraste (NL2SQL libre, VLM grandes), el diseño de ARES opta deliberadamente por un índice materializado, catálogo cerrado y LLM local pequeño, como se argumenta en los capítulos 03 y 04.
