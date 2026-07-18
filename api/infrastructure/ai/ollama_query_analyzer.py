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
2. Identificar si el usuario busca una clase de objeto (search_class).
3. Normalizar el concepto a canonical_label en inglés.
4. Devolver clase_yolo_candidates usando el catálogo.

Catálogo de clases disponibles:
{catalog}

Reglas:
- Si la consulta pide buscar un tipo de objeto, intent=search_class.
- Si combina clase y atributo (ej. "coches rojos", "red cars"), intent=search_class.
- Si pide solo atributos sin clase clara, intent=search_attribute.
- Si no entiendes la consulta, intent=unknown.
- clase_yolo_candidates debe contener solo valores del catálogo.
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
