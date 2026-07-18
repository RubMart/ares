from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

from config import settings
from domain.services.query_analyzer import QueryAnalyzer, QueryAnalyzerError
from domain.value_objects.semantic_query import StructuredQuery
from infrastructure.ai.yolo_class_catalog import (
    apply_catalog_fallback,
    build_catalog_prompt_section,
)


SYSTEM_PROMPT = """Eres un analizador semántico para búsquedas geoespaciales de detecciones YOLO.

La consulta del usuario puede estar en español o inglés.
Debes:
1. Detectar el idioma (es, en o unknown).
2. Identificar el intent (search_class, search_spatial, search_attribute o unknown).
3. Normalizar conceptos a canonical labels en inglés del catálogo.
4. Devolver clases YOLO usando el catálogo.

Catálogo de clases disponibles:
{catalog}

Reglas de intent:
- Si la consulta pide un tipo de objeto sin relación espacial, intent=search_class.
- Si combina clase y atributo (ej. "coches rojos", "red cars"), intent=search_class.
- Si pide proximidad entre dos objetos (ej. "coches cerca de rotonda", "cars near buildings"), intent=search_spatial.
- Si pide solo atributos sin clase clara, intent=search_attribute.
- Si no entiendes la consulta, intent=unknown.

Reglas espaciales (search_spatial):
- En "X cerca de Y" / "X near Y": X es el TARGET (lo que se busca y se devuelve), Y es la REFERENCE (ancla espacial).
- Rellena target_label, target_canonical_label, target_clase_yolo.
- Rellena reference_label, reference_canonical_label, reference_clase_yolo.
- relation="near" para cerca de / junto a / near / next to / close to.
- relation="inside" solo si pide claramente dentro/inside (aún limitado).
- distance_m=null salvo que el usuario indique metros explícitos.
- También rellena object_label/canonical_label/clase_yolo_candidates con los valores del TARGET (compatibilidad).

Reglas generales:
- clase_yolo_candidates y target_clase_yolo / reference_clase_yolo deben contener solo valores del catálogo.
- attributes vacío si el usuario no pide atributos concretos.
- attributes en inglés y forma canónica (ej. rojo/rojos -> "red", azul -> "blue").
- Colores admitidos: red, blue, green, black, white, yellow, gray, orange.
- reasoning breve en el idioma detectado.
"""


class OllamaQueryAnalyzer(QueryAnalyzer):
    def __init__(self) -> None:
        self._llm = ChatOllama(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            temperature=settings.ollama_temperature,
        ).with_structured_output(StructuredQuery)
        self._system_prompt = SYSTEM_PROMPT.format(
            catalog=build_catalog_prompt_section()
        )

    async def analyze(self, query: str) -> StructuredQuery:
        messages = [
            SystemMessage(content=self._system_prompt),
            HumanMessage(content=query.strip()),
        ]
        try:
            structured: StructuredQuery = await self._llm.ainvoke(messages)
        except Exception as exc:
            raise QueryAnalyzerError(
                f"No se pudo analizar la consulta con Ollama ({settings.ollama_model}): {exc}"
            ) from exc

        return apply_catalog_fallback(structured, query.strip())
