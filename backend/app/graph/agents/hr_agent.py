"""
HR Agent
=========
Evaluates culture fit, motivation, and past experience.
References specific companies and roles from the resume.
"""

from __future__ import annotations

import json
import logging

from langchain_core.messages import AIMessage

from app.config import get_settings
from app.graph.prompts import (
    HR_PROMPT,
    TONE_MAP,
    format_companies,
    format_projects,
    format_transcript,
)
from app.models.state import SessionState
from app.services.llm_provider import get_chat_model

logger = logging.getLogger(__name__)


async def hr_agent(state: SessionState) -> dict:
    """HR Interviewer node — asks culture-fit and experience questions."""
    settings = get_settings()
    highlights = state.get("resume_highlights", {})

    # Build the prompt with resume context
    prompt = HR_PROMPT.format(
        difficulty=state["difficulty"],
        job_role=state["job_role"],
        tone=TONE_MAP.get(state["difficulty"], TONE_MAP["medium"]),
        skills=", ".join(highlights.get("skills", [])[:10]),
        projects=format_projects(highlights.get("projects", [])),
        companies=format_companies(highlights.get("companies", [])),
        education=", ".join(
            f"{e.get('degree', '')} from {e.get('institution', '')}"
            for e in highlights.get("education", [])
        ),
        resume_excerpt=state.get("resume_text", "")[:settings.RESUME_TEXT_MAX_CHARS],
        job_description=state["job_description"][:1000],
        transcript=format_transcript(state.get("messages", [])),
    )

    llm = get_chat_model(temperature=0.7)

    try:
        response = await llm.ainvoke(prompt)
        content = response.content.strip()

        # Parse JSON response
        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("```", 1)[0]

        parsed = json.loads(content)
        question = parsed.get("question", "Tell me about your experience.")
        private_score = parsed.get("private_score", {})
        resume_ref = parsed.get("resume_reference")

        # Build the score entry
        score_entry = {
            "agent": "hr",
            "dimension": private_score.get("dimension", "culture_fit"),
            "score": max(0, min(10, private_score.get("score", 5))),
            "reasoning": private_score.get("reasoning", ""),
            "resume_reference": resume_ref,
        }

        logger.info(f"HR agent asked: {question[:80]}...")

        return {
            "messages": [AIMessage(content=question, name="hr")],
            "current_agent": "hr",
            "agent_history": state.get("agent_history", []) + ["hr"],
            "private_scores": state.get("private_scores", []) + [score_entry],
            "latest_agent_response": question,
        }

    except (json.JSONDecodeError, Exception) as e:
        logger.warning(f"HR agent JSON parse failed, using raw response: {e}")
        fallback = "Tell me about yourself and what draws you to this role."
        if hasattr(response, "content"):
            # Try to extract just the question from the response
            fallback = response.content.strip()[:500]

        return {
            "messages": [AIMessage(content=fallback, name="hr")],
            "current_agent": "hr",
            "agent_history": state.get("agent_history", []) + ["hr"],
            "private_scores": state.get("private_scores", []),
            "latest_agent_response": fallback,
        }
