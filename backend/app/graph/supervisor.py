"""
Deterministic supervisor for V1 interview routing.
"""

from __future__ import annotations

from app.models.state import SessionState


AGENT_ORDER = ["hr", "technical", "behavioral"]


def supervisor_route(state: SessionState) -> str:
    """Choose the next node using deterministic rotation only."""
    if state.get("status") == "completed":
        return "__end__"

    asked_questions = state.get("asked_questions", 0)
    max_turns = state.get("max_turns", 0)

    if asked_questions >= max_turns:
        return "synthesizer"

    return AGENT_ORDER[asked_questions % len(AGENT_ORDER)]
