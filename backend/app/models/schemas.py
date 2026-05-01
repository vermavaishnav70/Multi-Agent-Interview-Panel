"""
Pydantic Schemas — Request / Response Models
=============================================
Validation layer between the API boundary and internal logic.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ── Request Models ────────────────────────────────────────────────

class SessionCreateRequest(BaseModel):
    """Fields sent alongside the multipart form (resume file sent separately)."""
    job_role: str = Field(..., min_length=1, max_length=200, examples=["SDE Intern at Stripe"])
    job_description: str = Field(..., min_length=10, max_length=5000)
    difficulty: str = Field(default="medium", pattern="^(easy|medium|hard)$")
    voice_mode: bool = False
    max_turns: int = Field(default=9, ge=3, le=30)


class AnswerRequest(BaseModel):
    """User's answer to an agent's question."""
    content: str = Field(..., min_length=1, max_length=5000)


class TurnRequest(BaseModel):
    """Turn request for the unified streaming endpoint."""
    content: str = Field(default="", max_length=5000)
    transcribed_text: str | None = Field(default=None, max_length=5000)
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=200)


# ── Response Models ───────────────────────────────────────────────

class SessionResponse(BaseModel):
    """Returned after creating a session."""
    session_id: str
    status: str
    job_role: str
    difficulty: str
    max_turns: int
    voice_mode: bool
    created_at: datetime


class MessageResponse(BaseModel):
    """A single transcript message."""
    id: str
    role: str
    agent_name: Optional[str] = None
    content: str
    audio_url: Optional[str] = None
    timestamp: datetime


class TranscriptResponse(BaseModel):
    """Whisper transcription result."""
    transcript: str


class AgentScore(BaseModel):
    """A private score from one agent on one dimension."""
    agent: str
    dimension: str
    score: int = Field(ge=0, le=10)
    reasoning: str


class ResumeAccuracy(BaseModel):
    """Resume cross-reference results from Synthesizer."""
    verified_claims: list[str] = []
    unverified_claims: list[str] = []
    inflated_claims: list[str] = []


class ScorecardResponse(BaseModel):
    """Full scorecard returned to frontend."""
    session_id: str
    summary: str
    strengths: list[str]
    improvement_areas: list[str]
    resume_accuracy: ResumeAccuracy
    per_dimension_scores: dict[str, int]
    final_score: int
    hire_recommendation: str


class HealthResponse(BaseModel):
    """Health check."""
    status: str = "ok"
    version: str = "0.1.0"
