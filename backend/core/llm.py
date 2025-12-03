"""
PG Index Agents - Cliente de modelos de lenguaje
https://github.com/686f6c61/pg-index-agents

Este modulo configura y proporciona acceso a modelos de lenguaje a traves de OpenRouter.
OpenRouter actua como gateway que permite acceder a diferentes proveedores de LLM
(OpenAI, Anthropic, Google, etc.) con una unica API.

El modulo define diferentes configuraciones de LLM optimizadas para distintos casos
de uso: analisis tecnico, generacion de reportes y creacion de propuestas SQL.

Autor: 686f6c61
Licencia: MIT
"""

import asyncio
from typing import List, Union
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage
from .config import settings


def get_llm(temperature: float = 0.3, max_tokens: int = 4096) -> ChatOpenAI:
    """
    Crea un cliente LLM configurado para OpenRouter.

    La temperatura controla la aleatoriedad de las respuestas. Valores bajos
    producen respuestas mas deterministas, mientras que valores altos permiten
    mayor creatividad pero menor consistencia.

    Args:
        temperature: Temperatura de muestreo entre 0.0 y 1.0.
                    0.0 = respuestas deterministicas
                    1.0 = maxima creatividad
        max_tokens: Numero maximo de tokens en la respuesta.

    Returns:
        Instancia de ChatOpenAI configurada para usar OpenRouter.

    Note:
        Los headers HTTP-Referer y X-Title son requeridos por OpenRouter
        para identificar la aplicacion que realiza las peticiones.
    """
    return ChatOpenAI(
        model=settings.llm_model,
        openai_api_key=settings.openrouter_api_key,
        openai_api_base=settings.openrouter_base_url,
        temperature=temperature,
        max_tokens=max_tokens,
        default_headers={
            "HTTP-Referer": "http://localhost:8000",
            "X-Title": "PostgreSQL Index Agents"
        }
    )


def get_llm_for_analysis() -> ChatOpenAI:
    """
    Obtiene un LLM configurado para analisis tecnico.

    Usa una temperatura moderada (0.3) que permite cierta variabilidad
    en el analisis mientras mantiene coherencia. Adecuado para tareas
    como clasificacion de tablas, deteccion de patrones y evaluacion
    de estructuras de indices.

    Returns:
        Cliente LLM con configuracion balanceada.
    """
    return get_llm(temperature=0.3, max_tokens=4096)


def get_llm_for_reports() -> ChatOpenAI:
    """
    Obtiene un LLM configurado para generacion de reportes.

    Usa una temperatura mas alta (0.5) para producir texto mas natural
    y variado en los reportes. El limite de tokens es mayor (8192) para
    permitir reportes detallados con multiples secciones.

    Returns:
        Cliente LLM optimizado para generacion de texto extenso.
    """
    return get_llm(temperature=0.5, max_tokens=8192)


def get_llm_for_proposals() -> ChatOpenAI:
    """
    Obtiene un LLM configurado para generacion de propuestas SQL.

    Usa la temperatura mas baja (0.1) para maximizar la precision
    y consistencia del codigo SQL generado. Las propuestas de indices
    requieren exactitud sintactica y semantica.

    Returns:
        Cliente LLM optimizado para generacion de codigo SQL.
    """
    return get_llm(temperature=0.1, max_tokens=2048)


async def invoke_llm_async(
    llm: ChatOpenAI,
    messages: List[BaseMessage]
) -> BaseMessage:
    """
    Invoca el LLM de forma asincrona.

    Utiliza la interfaz asincrona nativa de LangChain (ainvoke) para
    evitar bloquear el event loop de asyncio durante las llamadas
    a la API.

    Args:
        llm: Cliente LLM configurado.
        messages: Lista de mensajes del historial de conversacion.

    Returns:
        Mensaje de respuesta del modelo.
    """
    return await llm.ainvoke(messages)


def invoke_llm_nonblocking(
    llm: ChatOpenAI,
    messages: List[BaseMessage]
) -> BaseMessage:
    """
    Invoca el LLM sin bloquear otras tareas asincronas.

    Esta funcion detecta si esta siendo ejecutada dentro de un contexto
    asincrono. Si es asi, ejecuta la llamada en un thread separado para
    evitar bloquear el event loop. Si no hay event loop activo, ejecuta
    la llamada de forma sincrona normal.

    Args:
        llm: Cliente LLM configurado.
        messages: Lista de mensajes del historial de conversacion.

    Returns:
        Mensaje de respuesta del modelo.

    Note:
        Esta funcion es util cuando se necesita llamar al LLM desde
        codigo que puede ejecutarse tanto en contexto sincrono como
        asincrono.
    """
    try:
        loop = asyncio.get_running_loop()
        # Estamos en contexto asincrono - ejecutar en thread pool
        # para no bloquear el event loop
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(llm.invoke, messages)
            return future.result()
    except RuntimeError:
        # No hay event loop activo - ejecutar de forma sincrona
        return llm.invoke(messages)
