"""
Centralized Configuration — Single Source of Truth
====================================================
All configurable values live here. Change a setting in .env and it
propagates everywhere. No magic strings scattered across the codebase.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file."""

    # ── LLM Providers ──────────────────────────────────────────────
    NIM_API_KEY: str = ""
    NIM_BASE_URL: str = "https://integrate.api.nvidia.com/v1"
    NIM_FAST_MODEL: str = "meta/llama-3.1-8b-instruct"
    NIM_STRONG_MODEL: str = "meta/llama-3.1-8b-instruct"
    GOOGLE_API_KEY: str = ""
    GEMINI_FAST_MODEL: str = "gemini-2.0-flash"
    GEMINI_STRONG_MODEL: str = "gemini-2.0-flash"
    GROQ_API_KEY: str = ""
    GROQ_FAST_MODEL: str = "llama-3.3-70b-versatile"
    GROQ_STRONG_MODEL: str = "llama-3.3-70b-versatile"

    # ── Voice — STT / TTS ─────────────────────────────────────────
    SARVAM_API_KEY: str = ""
    ELEVENLABS_API_KEY: str = ""
    ELEVENLABS_STT_MODEL: str = "scribe_v2"
    SARVAM_STT_MODEL: str = "saaras:v3"
    SARVAM_STT_MODE: str = "transcribe"
    SARVAM_STT_LANGUAGE: str = "unknown"
    SARVAM_TTS_MODEL: str = "bulbul:v3"
    SARVAM_TTS_LANGUAGE: str = "en-IN"
    SARVAM_TTS_OUTPUT_CODEC: str = "mp3"
    NIM_TTS_URL: str = ""
    NIM_TTS_MODEL: str = ""
    NIM_STT_URL: str = ""
    NIM_STT_MODEL: str = ""
    NIM_STT_FUNCTION_ID: str = ""
    NIM_STT_LANGUAGE: str = "en"
    NIM_TTS_FUNCTION_ID: str = ""
    NIM_TTS_LANGUAGE: str = "en-US"
    NIM_TTS_SAMPLE_RATE: int = 22050
    NIM_TTS_ZERO_SHOT_QUALITY: int = 20
    NIM_TTS_PROMPT_FILE: str = ""
    NIM_TTS_PROMPT_TRANSCRIPT: str = ""

    # ── Interview Defaults ────────────────────────────────────────
    DEFAULT_MAX_TURNS: int = 9
    RESUME_TEXT_MAX_CHARS: int = 2000
    RESUME_EXTRACT_MAX_CHARS: int = 3000
    MAX_CONSECUTIVE_SAME_AGENT: int = 2

    # ── Database ──────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@db.project-ref.supabase.co:5432/postgres"

    # ── Server ────────────────────────────────────────────────────
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]
    FRONTEND_URL: str = "http://localhost:3000"
    BACKEND_URL: str = "http://localhost:8000"

    # ── MCP Toolbox ───────────────────────────────────────────────
    TOOLBOX_URL: str = "http://localhost:5000"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    """Cached singleton — import this everywhere instead of constructing Settings directly."""
    return Settings()
