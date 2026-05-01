"""
LLM Provider Factory
=====================
Creates LangChain LLM instances with native fallback chains (NVIDIA -> Gemini -> Groq)
and fast-failing to prevent quota stalls.
"""

from __future__ import annotations

import logging

from langchain_core.language_models import BaseChatModel

from app.config import get_settings

logger = logging.getLogger(__name__)


def _create_nim(model: str | None = None, temperature: float = 0.7) -> BaseChatModel:
    """Create an NVIDIA NIM chat model."""
    from langchain_openai import ChatOpenAI

    settings = get_settings()
    return ChatOpenAI(
        base_url=settings.NIM_BASE_URL,
        api_key=settings.NIM_API_KEY,
        model=model or settings.NIM_FAST_MODEL,
        temperature=temperature,
        max_retries=0,  # Fail fast to allow fallbacks
    )


def _create_gemini(model: str | None = None, temperature: float = 0.7) -> BaseChatModel:
    """Create a Google Gemini chat model."""
    from langchain_google_genai import ChatGoogleGenerativeAI

    settings = get_settings()
    return ChatGoogleGenerativeAI(
        model=model or settings.GEMINI_FAST_MODEL,
        google_api_key=settings.GOOGLE_API_KEY,
        temperature=temperature,
        convert_system_message_to_human=True,
        max_retries=0,  # Fail fast to allow fallbacks
    )


def _create_groq(model: str | None = None, temperature: float = 0.7) -> BaseChatModel:
    """Create a Groq chat model."""
    from langchain_groq import ChatGroq

    settings = get_settings()
    return ChatGroq(
        model=model or settings.GROQ_FAST_MODEL,
        groq_api_key=settings.GROQ_API_KEY,
        temperature=temperature,
        max_retries=0,  # Fail fast to allow fallbacks
    )


def get_chat_model(
    provider: str | None = None,
    model: str | None = None,
    temperature: float = 0.7,
) -> BaseChatModel:
    """
    Get a chat model instance with automatic fallback routing.
    Chain: NIM -> Gemini -> Groq.

    Args:
        provider: Override to force a specific provider ("nim", "gemini" or "groq").
        model: Override the default model for the chosen provider.
        temperature: Sampling temperature.

    Returns:
        A LangChain BaseChatModel instance (with fallbacks attached if no provider forced).
    """
    settings = get_settings()
    
    # If a specific provider is requested, bypass fallbacks
    if provider:
        if provider == "nim":
            return _create_nim(model, temperature)
        elif provider == "gemini":
            return _create_gemini(model, temperature)
        elif provider == "groq":
            return _create_groq(model, temperature)
        else:
            raise ValueError(f"Unknown LLM provider: {provider}")

    llms = []
    
    if settings.NIM_API_KEY:
        try:
            llms.append(_create_nim(model=model or settings.NIM_FAST_MODEL, temperature=temperature))
        except Exception as e:
            logger.warning(f"Failed to initialize NIM: {e}")
            
    if settings.GOOGLE_API_KEY:
        try:
            llms.append(_create_gemini(model=model or settings.GEMINI_FAST_MODEL, temperature=temperature))
        except Exception as e:
            logger.warning(f"Failed to initialize Gemini: {e}")
            
    if settings.GROQ_API_KEY:
        try:
            llms.append(_create_groq(model=model or settings.GROQ_FAST_MODEL, temperature=temperature))
        except Exception as e:
            logger.warning(f"Failed to initialize Groq: {e}")

    if not llms:
        raise ValueError("No LLM providers configured in .env (need NIM, GOOGLE, or GROQ)")

    primary_llm = llms[0]
    if len(llms) > 1:
        primary_llm = primary_llm.with_fallbacks(llms[1:])
        
    return primary_llm


def get_fast_model(temperature: float = 0.3) -> BaseChatModel:
    """Get a fast model for utility tasks (resume parsing, routing)."""
    return get_chat_model(temperature=temperature)


def get_strong_model(temperature: float = 0.4) -> BaseChatModel:
    """Get the strongest available model for complex tasks (synthesizer)."""
    settings = get_settings()
    
    llms = []
    
    if settings.NIM_API_KEY:
        try:
            llms.append(_create_nim(model=settings.NIM_STRONG_MODEL, temperature=temperature))
        except Exception as e:
            logger.warning(f"Failed to initialize NIM Strong: {e}")
            
    if settings.GOOGLE_API_KEY:
        try:
            llms.append(_create_gemini(model=settings.GEMINI_STRONG_MODEL, temperature=temperature))
        except Exception as e:
            logger.warning(f"Failed to initialize Gemini Strong: {e}")
            
    if settings.GROQ_API_KEY:
        try:
            llms.append(_create_groq(model=settings.GROQ_STRONG_MODEL, temperature=temperature))
        except Exception as e:
            logger.warning(f"Failed to initialize Groq Strong: {e}")

    if not llms:
        raise ValueError("No LLM providers configured in .env (need NIM, GOOGLE, or GROQ)")

    primary_llm = llms[0]
    if len(llms) > 1:
        primary_llm = primary_llm.with_fallbacks(llms[1:])
        
    return primary_llm
