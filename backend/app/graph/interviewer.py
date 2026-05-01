"""
Interviewer prompt helpers for V1.
"""

from __future__ import annotations

from app.graph.prompts import build_interviewer_prompt, format_recent_transcript
from app.models.state import SessionState


def build_question_prompt(agent_name: str, state: SessionState) -> str:
    return build_interviewer_prompt(
        agent_name=agent_name,
        difficulty=state["difficulty"],
        job_role=state["job_role"],
        job_description=state["job_description"],
        resume_context=state.get("resume_context", {}),
        transcript=format_recent_transcript(state.get("messages", []), last_n=4),
    )
