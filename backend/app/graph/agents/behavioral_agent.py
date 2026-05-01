"""
Behavioral Agent
=================
Evaluates communication, leadership, and behavioral competencies.
Uses STAR format questions anchored to resume experiences.
"""

from __future__ import annotations

import json
import logging

from langchain_core.messages import AIMessage

from app.config import get_settings
from app.graph.prompts import (
    BEHAVIORAL_PROMPT,
    TONE_MAP,
    format_companies,
    format_projects,
    format_transcript,
)
from app.models.state import SessionState
from app.services.llm_provider import get_chat_model

logger = logging.getLogger(__name__)


async def behavioral_agent(state: SessionState) -> dict:
    """Behavioral Coach node — STAR questions, communication assessment."""
    settings = get_settings()
    highlights = state.get("resume_highlights", {})

    prompt = BEHAVIORAL_PROMPT.format(
        difficulty=state["difficulty"],
        job_role=state["job_role"],
        tone=TONE_MAP.get(state["difficulty"], TONE_MAP["medium"]),
        companies=format_companies(highlights.get("companies", [])),
        projects=format_projects(highlights.get("projects", [])),
        resume_excerpt=state.get("resume_text", "")[:settings.RESUME_TEXT_MAX_CHARS],
        job_description=state["job_description"][:1000],
        transcript=format_transcript(state.get("messages", [])),
    )

    llm = get_chat_model(temperature=0.75)

    try:
        response = await llm.ainvoke(prompt)
        content = response.content.strip()

        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("```", 1)[0]

        parsed = json.loads(content)
        question = parsed.get("question", "Tell me about a challenging situation you faced.")
        private_score = parsed.get("private_score", {})
        resume_ref = parsed.get("resume_reference")

        score_entry = {
            "agent": "behavioral",
            "dimension": private_score.get("dimension", "communication"),
            "score": max(0, min(10, private_score.get("score", 5))),
            "reasoning": private_score.get("reasoning", ""),
            "resume_reference": resume_ref,
        }

        logger.info(f"Behavioral agent asked: {question[:80]}...")

        return {
            "messages": [AIMessage(content=question, name="behavioral")],
            "current_agent": "behavioral",
            "agent_history": state.get("agent_history", []) + ["behavioral"],
            "private_scores": state.get("private_scores", []) + [score_entry],
            "latest_agent_response": question,
        }

    except (json.JSONDecodeError, Exception) as e:
        logger.warning(f"Behavioral agent JSON parse failed: {e}")
        fallback = "Tell me about a time you had to handle a difficult situation at work."
        if hasattr(response, "content"):
            fallback = response.content.strip()[:500]

        return {
            "messages": [AIMessage(content=fallback, name="behavioral")],
            "current_agent": "behavioral",
            "agent_history": state.get("agent_history", []) + ["behavioral"],
            "private_scores": state.get("private_scores", []),
            "latest_agent_response": fallback,
        }
