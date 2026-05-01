"""
Prompt templates and formatting helpers for the V1 turn pipeline.
"""

from __future__ import annotations

from typing import Any


TONE_MAP = {
    "easy": "Friendly, encouraging, and supportive. Keep questions clear and accessible.",
    "medium": "Professional, balanced, and moderately challenging.",
    "hard": "Rigorous, probing, and demanding. Push for depth and concrete detail.",
}

AGENT_DIMENSIONS = {
    "hr": "culture_fit",
    "technical": "technical_depth",
    "behavioral": "communication",
}


def summarize_job_description(job_description: str, limit: int = 900) -> str:
    return " ".join(job_description.split())[:limit] or "No job description provided."


def format_recent_transcript(messages: list[Any], last_n: int = 4) -> str:
    recent = messages[-last_n:] if len(messages) > last_n else messages
    lines: list[str] = []
    for message in recent:
        content = getattr(message, "content", str(message))
        role = getattr(message, "name", None) or (
            "Candidate" if getattr(message, "type", "") == "human" else "Interviewer"
        )
        lines.append(f"[{role}] {content}")
    return "\n".join(lines) if lines else "(No prior transcript)"


def format_private_scores(scores: list[dict[str, Any]]) -> str:
    if not scores:
        return "No evaluator scores yet."

    lines = []
    for score in scores:
        reference = score.get("resume_reference")
        suffix = f" (ref: {reference})" if reference else ""
        lines.append(
            f"- {score.get('agent', '?')} | {score.get('dimension', '?')} | "
            f"{score.get('score', '?')}/10 | {score.get('reasoning', 'N/A')}{suffix}"
        )
    return "\n".join(lines)


def format_projects(projects: list[dict[str, Any]]) -> str:
    return "\n".join(
        f"- {project.get('name', 'Unnamed')}: {project.get('description', 'No description')}"
        for project in projects[:5]
    ) or "- None"


def format_companies(companies: list[dict[str, Any]]) -> str:
    return "\n".join(
        f"- {company.get('role', 'Unknown')} at {company.get('name', 'Unknown')} "
        f"({company.get('duration', 'N/A')})"
        for company in companies[:5]
    ) or "- None"


def format_transcript(messages: list[Any], last_n: int = 6) -> str:
    return format_recent_transcript(messages, last_n=last_n)


def format_resume_context(resume_context: dict[str, Any]) -> str:
    skills = ", ".join(resume_context.get("skills", [])) or "None"
    projects = "\n".join(
        f"- {project.get('name', 'Unnamed')}: {project.get('description', 'No description')} "
        f"[{', '.join(project.get('tech_stack', []))}]"
        for project in resume_context.get("projects", [])
    ) or "- None"
    companies = "\n".join(
        f"- {company.get('role', 'Unknown')} at {company.get('name', 'Unknown')} "
        f"({company.get('duration', 'N/A')})"
        for company in resume_context.get("companies", [])
    ) or "- None"
    education = "\n".join(
        f"- {item.get('degree', 'Unknown degree')} at {item.get('institution', 'Unknown institution')} "
        f"({item.get('year', 'N/A')})"
        for item in resume_context.get("education", [])
    ) or "- None"
    claims = "\n".join(f"- {claim}" for claim in resume_context.get("anchored_claims", [])) or "- None"
    excerpt = resume_context.get("resume_excerpt", "") or "None"

    return (
        f"Skills: {skills}\n"
        f"Projects:\n{projects}\n"
        f"Companies:\n{companies}\n"
        f"Education:\n{education}\n"
        f"Anchored claims:\n{claims}\n"
        f"Short excerpt: {excerpt}"
    )


def build_interviewer_prompt(
    agent_name: str,
    difficulty: str,
    job_role: str,
    job_description: str,
    resume_context: dict[str, Any],
    transcript: str,
) -> str:
    focus_map = {
        "hr": "culture fit, motivation, teamwork, and candidate intent",
        "technical": "technical depth, architecture choices, debugging, and implementation trade-offs",
        "behavioral": "communication, leadership, ownership, and STAR-style storytelling",
    }
    tone = TONE_MAP.get(difficulty, TONE_MAP["medium"])
    focus = focus_map.get(agent_name, "candidate evaluation")

    return f"""You are the {agent_name.upper()} interviewer for a {job_role} interview.
Tone: {tone}
Focus area: {focus}

=== JOB DESCRIPTION SUMMARY ===
{summarize_job_description(job_description)}

=== COMPACT RESUME CONTEXT ===
{format_resume_context(resume_context)}

=== RECENT TRANSCRIPT ===
{transcript}

=== INSTRUCTIONS ===
Ask exactly one focused interview question.
You may ask a follow-up if it clearly builds on the most recent answer.
Reference resume details when helpful, but do not quote long resume excerpts.
Return ONLY the question text. No bullets, no preamble, no JSON, no markdown.
""".strip()


HR_PROMPT = (
    "You are an HR interviewer for {job_role}.\n"
    "Tone: {tone}\n"
    "Projects:\n{projects}\n"
    "Companies:\n{companies}\n"
    "Education: {education}\n"
    "Transcript:\n{transcript}\n"
    "Ask one concise question and return only JSON if the caller expects it."
)


TECHNICAL_PROMPT = (
    "You are a technical interviewer for {job_role}.\n"
    "Tone: {tone}\n"
    "Skills: {skills}\n"
    "Projects:\n{projects}\n"
    "Companies:\n{companies}\n"
    "Transcript:\n{transcript}\n"
    "Ask one concise technical question and return only JSON if the caller expects it."
)


BEHAVIORAL_PROMPT = (
    "You are a behavioral interviewer for {job_role}.\n"
    "Tone: {tone}\n"
    "Projects:\n{projects}\n"
    "Companies:\n{companies}\n"
    "Transcript:\n{transcript}\n"
    "Ask one concise behavioral question and return only JSON if the caller expects it."
)


EVALUATOR_PROMPT = """You are the evaluator for a multi-agent interview panel.

Evaluate the candidate's most recent answer against the prior interviewer question.
Use the resume context only to judge whether the answer supports or weakens resume claims.

Return ONLY valid JSON with this exact shape:
{
  "dimension": "culture_fit",
  "score": 0,
  "reasoning": "brief justification",
  "resume_reference": "optional short reference or null"
}

Scoring guidance:
- 0-3: weak or evasive answer
- 4-6: partial answer with gaps
- 7-8: strong, credible answer
- 9-10: excellent, detailed, highly credible answer
"""


SYNTHESIZER_PROMPT = """You are the final synthesizer for a multi-agent interview panel.

You will receive:
- compact resume context
- the full interview transcript
- evaluator scores collected after each candidate answer

Return ONLY valid JSON with this exact shape:
{
  "summary": "2-3 sentence overall assessment",
  "strengths": ["strength 1", "strength 2", "strength 3"],
  "improvement_areas": ["area 1", "area 2"],
  "resume_accuracy": {
    "verified_claims": ["claim 1"],
    "unverified_claims": ["claim 2"],
    "inflated_claims": ["claim 3"]
  },
  "per_dimension_scores": {
    "communication": 0,
    "problem_solving": 0,
    "technical_depth": 0,
    "culture_fit": 0
  },
  "final_score": 0,
  "hire_recommendation": "borderline"
}

Valid hire_recommendation values:
- "strong_yes"
- "yes"
- "borderline"
- "no"
"""
