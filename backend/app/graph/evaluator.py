"""
Evaluator prompt helpers for V1.
"""

from __future__ import annotations

from app.graph.prompts import EVALUATOR_PROMPT, format_resume_context


def build_evaluator_prompt(
    *,
    agent_name: str,
    previous_question: str,
    latest_answer: str,
    resume_context: dict,
    difficulty: str,
) -> tuple[str, str]:
    user_prompt = f"""Difficulty: {difficulty}
Interviewer: {agent_name}

=== COMPACT RESUME CONTEXT ===
{format_resume_context(resume_context)}

=== PREVIOUS INTERVIEWER QUESTION ===
{previous_question}

=== LATEST CANDIDATE ANSWER ===
{latest_answer}
"""
    return EVALUATOR_PROMPT, user_prompt
