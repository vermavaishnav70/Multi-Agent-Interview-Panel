"""
Synthesizer Agent
==================
Cross-references resume claims against interview performance.
Produces the final structured scorecard JSON.
"""

from __future__ import annotations

import json
import logging

from langchain_core.messages import AIMessage

from app.graph.prompts import SYNTHESIZER_PROMPT, format_transcript
from app.models.state import SessionState
from app.services.llm_provider import get_strong_model

logger = logging.getLogger(__name__)


def _format_scores(scores: list[dict]) -> str:
    """Format private scores for the synthesizer prompt."""
    if not scores:
        return "No private scores recorded."
    lines = []
    for s in scores:
        lines.append(
            f"  • [{s.get('agent', '?')}] {s.get('dimension', '?')}: "
            f"{s.get('score', '?')}/10 — {s.get('reasoning', 'N/A')}"
            f"{' (ref: ' + s['resume_reference'] + ')' if s.get('resume_reference') else ''}"
        )
    return "\n".join(lines)


def _format_highlights(highlights: dict) -> str:
    """Format resume highlights for the synthesizer."""
    parts = []
    if highlights.get("skills"):
        parts.append(f"Skills: {', '.join(highlights['skills'][:15])}")
    if highlights.get("projects"):
        for p in highlights["projects"][:5]:
            parts.append(f"Project: {p.get('name', '?')} — {p.get('description', 'N/A')}")
    if highlights.get("companies"):
        for c in highlights["companies"][:5]:
            parts.append(f"Experience: {c.get('role', '?')} at {c.get('name', '?')} ({c.get('duration', 'N/A')})")
    return "\n".join(parts) if parts else "No resume highlights available."


async def synthesizer_agent(state: SessionState) -> dict:
    """Synthesizer node — produces final scorecard with resume cross-referencing."""
    highlights = state.get("resume_highlights", {})

    prompt = SYNTHESIZER_PROMPT.format(
        resume_highlights=_format_highlights(highlights),
        transcript=format_transcript(state.get("messages", []), last_n=50),
        private_scores=_format_scores(state.get("private_scores", [])),
        job_role=state["job_role"],
    )

    llm = get_strong_model(temperature=0.3)

    try:
        response = await llm.ainvoke(prompt)
        content = response.content.strip()

        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("```", 1)[0]

        scorecard = json.loads(content)

        # Validate and clamp scores
        for dim, score in scorecard.get("per_dimension_scores", {}).items():
            scorecard["per_dimension_scores"][dim] = max(0, min(10, score))
        scorecard["final_score"] = max(0, min(100, scorecard.get("final_score", 50)))

        valid_recs = {"strong_yes", "yes", "borderline", "no"}
        if scorecard.get("hire_recommendation") not in valid_recs:
            scorecard["hire_recommendation"] = "borderline"

        logger.info(
            f"Synthesizer completed: score={scorecard.get('final_score')}, "
            f"recommendation={scorecard.get('hire_recommendation')}"
        )

        summary_text = (
            f"Interview complete. Final score: {scorecard.get('final_score', 'N/A')}/100. "
            f"Recommendation: {scorecard.get('hire_recommendation', 'N/A')}. "
            f"{scorecard.get('summary', '')}"
        )

        return {
            "messages": [AIMessage(content=summary_text, name="synthesizer")],
            "scorecard": scorecard,
            "status": "completed",
            "current_agent": "synthesizer",
            "latest_agent_response": summary_text,
        }

    except (json.JSONDecodeError, Exception) as e:
        logger.error(f"Synthesizer failed to produce valid scorecard: {e}")

        # Produce a fallback scorecard
        fallback_scorecard = {
            "summary": "The interview was completed but the evaluation system encountered an error. Manual review recommended.",
            "strengths": ["Interview completed"],
            "improvement_areas": ["Unable to fully evaluate"],
            "resume_accuracy": {
                "verified_claims": [],
                "unverified_claims": [],
                "inflated_claims": [],
            },
            "per_dimension_scores": {
                "communication": 5,
                "problem_solving": 5,
                "technical_depth": 5,
                "culture_fit": 5,
            },
            "final_score": 50,
            "hire_recommendation": "borderline",
        }

        return {
            "messages": [AIMessage(
                content="Interview complete. Scorecard generated with limited data.",
                name="synthesizer",
            )],
            "scorecard": fallback_scorecard,
            "status": "completed",
            "current_agent": "synthesizer",
            "latest_agent_response": "Interview complete. Scorecard generated with limited data.",
        }
