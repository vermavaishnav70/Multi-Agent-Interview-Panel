"""
Resume Parser Service
======================
Extracts text from PDF resumes using PyMuPDF, then uses an LLM
to produce structured highlights (skills, projects, companies, education).
"""

from __future__ import annotations

import json
import logging

import fitz  # PyMuPDF

from app.config import get_settings
from app.services.provider_router import get_provider_router

logger = logging.getLogger(__name__)

# ── Extraction Prompt ─────────────────────────────────────────────

EXTRACTION_PROMPT = """You are a resume parser. Extract structured information from the following resume text.

Return a JSON object with exactly these keys:
- "skills": list of technical and soft skills mentioned (strings)
- "projects": list of objects with keys "name", "tech_stack" (list of strings), "description" (1-2 sentences)
- "companies": list of objects with keys "name", "role", "duration"
- "education": list of objects with keys "institution", "degree", "year"

Rules:
- Extract ONLY what is explicitly stated in the resume
- If a section is missing, return an empty list for that key
- Keep descriptions concise
- Return ONLY valid JSON, no preamble or explanation

Resume text:
{resume_text}"""


async def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """
    Extract raw text from a PDF using PyMuPDF.

    Args:
        pdf_bytes: Raw bytes of the uploaded PDF file.

    Returns:
        Extracted text string.
    """
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        pages = []
        for page in doc:
            text = page.get_text("text")
            if text:
                pages.append(text.strip())
        doc.close()

        raw_text = "\n\n".join(pages)
        logger.info(f"Extracted {len(raw_text)} chars from PDF ({len(pages)} pages)")
        return raw_text

    except Exception as e:
        logger.error(f"PDF extraction failed: {e}")
        raise ValueError(f"Could not parse the uploaded PDF: {e}")


async def extract_highlights(resume_text: str) -> dict:
    """
    Use LLM to extract structured highlights from resume text.

    Args:
        resume_text: Raw text extracted from the PDF.

    Returns:
        Dict with keys: skills, projects, companies, education.
    """
    settings = get_settings()
    truncated = resume_text[:settings.RESUME_EXTRACT_MAX_CHARS]

    try:
        router = get_provider_router()
        response = await router.generate_text(
            system_prompt="You are a resume parser. Return only valid JSON.",
            user_prompt=EXTRACTION_PROMPT.format(resume_text=truncated),
            tier="fast",
            temperature=0.1,
        )

        # Parse the JSON response
        content = response.strip()

        # Handle potential markdown code fences
        if content.startswith("```"):
            content = content.split("\n", 1)[1]  # Remove first line
            content = content.rsplit("```", 1)[0]  # Remove last fence

        highlights = json.loads(content)

        # Validate expected keys exist
        for key in ("skills", "projects", "companies", "education"):
            if key not in highlights:
                highlights[key] = []

        logger.info(
            f"Extracted highlights: {len(highlights.get('skills', []))} skills, "
            f"{len(highlights.get('projects', []))} projects, "
            f"{len(highlights.get('companies', []))} companies"
        )
        return highlights

    except json.JSONDecodeError as e:
        logger.warning(f"LLM returned invalid JSON for resume extraction: {e}")
        return {"skills": [], "projects": [], "companies": [], "education": []}
    except Exception as e:
        logger.error(f"Resume highlight extraction failed: {e}")
        return {"skills": [], "projects": [], "companies": [], "education": []}


async def parse_resume(pdf_bytes: bytes) -> dict:
    """
    Full resume parsing pipeline: PDF → text → structured highlights.

    Args:
        pdf_bytes: Raw bytes of the uploaded PDF.

    Returns:
        Dict with "raw_text" and "highlights".
    """
    raw_text = await extract_text_from_pdf(pdf_bytes)

    if not raw_text.strip():
        logger.warning("Resume PDF contained no extractable text")
        return {
            "raw_text": "",
            "highlights": {"skills": [], "projects": [], "companies": [], "education": []},
        }

    highlights = await extract_highlights(raw_text)

    return {
        "raw_text": raw_text,
        "highlights": highlights,
    }
