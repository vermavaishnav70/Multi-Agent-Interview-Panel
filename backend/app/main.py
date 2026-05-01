"""
FastAPI Application — Main Entry Point
========================================
Configures CORS, lifespan events, and includes all route routers.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.engine import make_url

from app.config import get_settings
from app.models.database import init_db, normalize_database_url
from app.models.schemas import HealthResponse
from app.routes import interview, scorecard, sessions, transcribe

# ── Logging ───────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-30s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def _safe_database_url(database_url: str) -> str:
    return make_url(normalize_database_url(database_url)).render_as_string(hide_password=True)


# ── Lifespan ──────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    settings = get_settings()
    logger.info("=" * 60)
    logger.info("Multi-Agent Interview Panel — Starting")
    logger.info("  LLM Routing: NIM -> Gemini -> Groq")
    logger.info("  Voice STT:    NVIDIA Whisper -> Sarvam")
    logger.info("  Voice Agents: NVIDIA TTS -> Sarvam")
    logger.info(f"  Database:     {_safe_database_url(settings.DATABASE_URL)}")
    logger.info(f"  CORS Origins: {settings.CORS_ORIGINS}")
    logger.info("=" * 60)

    # Initialize database tables
    await init_db()
    logger.info("Database initialized")

    # Pre-compile the graph (lazy singleton, but warm up)
    from app.graph.builder import get_interview_graph
    get_interview_graph()
    logger.info("Interview graph compiled")

    yield  # App is running

    logger.info("Shutting down...")


# ── App ───────────────────────────────────────────────────────────

app = FastAPI(
    title="Multi-Agent Interview Panel",
    description="AI-powered interview panel with resume parsing, voice I/O, and multi-agent evaluation.",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ────────────────────────────────────────────────────────

app.include_router(sessions.router, prefix="/api")
app.include_router(interview.router, prefix="/api")
app.include_router(transcribe.router, prefix="/api")
app.include_router(scorecard.router, prefix="/api")


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse()


@app.get("/")
async def root():
    """Root redirect to API docs."""
    return {
        "message": "Multi-Agent Interview Panel API",
        "docs": "/docs",
        "health": "/health",
    }
