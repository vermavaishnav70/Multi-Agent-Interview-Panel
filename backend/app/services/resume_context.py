"""
Resume context compaction helpers.
"""

from __future__ import annotations

from typing import Any


def _trim_list(values: list[str], limit: int) -> list[str]:
    return [value.strip() for value in values if isinstance(value, str) and value.strip()][:limit]


def _compact_projects(projects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    for project in projects[:3]:
        compact.append(
            {
                "name": str(project.get("name", "")).strip(),
                "description": str(project.get("description", "")).strip()[:220],
                "tech_stack": _trim_list(project.get("tech_stack", []), 6),
            }
        )
    return compact


def _compact_companies(companies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    for company in companies[:3]:
        compact.append(
            {
                "name": str(company.get("name", "")).strip(),
                "role": str(company.get("role", "")).strip(),
                "duration": str(company.get("duration", "")).strip(),
            }
        )
    return compact


def _compact_education(education: list[dict[str, Any]]) -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    for item in education[:2]:
        compact.append(
            {
                "institution": str(item.get("institution", "")).strip(),
                "degree": str(item.get("degree", "")).strip(),
                "year": str(item.get("year", "")).strip(),
            }
        )
    return compact


def _build_anchored_claims(highlights: dict[str, Any]) -> list[str]:
    claims: list[str] = []

    for project in highlights.get("projects", [])[:2]:
        name = str(project.get("name", "")).strip()
        tech = ", ".join(_trim_list(project.get("tech_stack", []), 4))
        if name and tech:
            claims.append(f"Built {name} using {tech}")
        elif name:
            claims.append(f"Claims hands-on experience with project {name}")

    for company in highlights.get("companies", [])[:2]:
        role = str(company.get("role", "")).strip()
        name = str(company.get("name", "")).strip()
        duration = str(company.get("duration", "")).strip()
        if role and name:
            suffix = f" for {duration}" if duration else ""
            claims.append(f"Worked as {role} at {name}{suffix}")

    for skill in _trim_list(highlights.get("skills", []), 2):
        claims.append(f"Claims working knowledge of {skill}")

    deduped: list[str] = []
    seen = set()
    for claim in claims:
        if claim not in seen:
            deduped.append(claim)
            seen.add(claim)
    return deduped[:5]


def build_resume_context(highlights: dict[str, Any], resume_text: str = "") -> dict[str, Any]:
    """Create a compact resume context that is safe to inject into prompts repeatedly."""
    safe_highlights = highlights or {}
    context = {
        "skills": _trim_list(safe_highlights.get("skills", []), 8),
        "projects": _compact_projects(safe_highlights.get("projects", [])),
        "companies": _compact_companies(safe_highlights.get("companies", [])),
        "education": _compact_education(safe_highlights.get("education", [])),
        "anchored_claims": _build_anchored_claims(safe_highlights),
        "resume_excerpt": " ".join(resume_text.split())[:400],
    }

    return context
