"""
LangGraph Session State
========================
Typed state shared across all graph nodes (supervisor + agents).
"""

from __future__ import annotations

from typing import Annotated, TypedDict

from langgraph.graph import add_messages


class AgentScoreEntry(TypedDict):
    """Private score from a single agent turn."""
    agent: str
    dimension: str
    score: int
    reasoning: str
    resume_reference: str | None


class SessionState(TypedDict):
    """
    Shared state for a single interview session.
    Passed through all LangGraph nodes.
    """

    # ── Identity ──
    session_id: str
    job_role: str
    job_description: str

    # ── Resume ──
    resume_text: str
    resume_highlights: dict  # {skills, projects, companies, education}
    resume_context: dict

    # ── Interview Flow ──
    turn_count: int
    asked_questions: int
    max_turns: int
    messages: Annotated[list, add_messages]
    current_agent: str
    agent_history: list[str]  # track sequence for loop guards
    difficulty: str  # "easy" | "medium" | "hard"

    # ── Scoring ──
    private_scores: list[AgentScoreEntry]

    # ── Status ──
    status: str  # "active" | "synthesizing" | "completed"
    scorecard: dict | None
    voice_mode: bool
    latest_agent_response: str  # last agent response text (for TTS streaming)
    last_resume_reference: str | None
