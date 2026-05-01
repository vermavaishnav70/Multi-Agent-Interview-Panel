"""
Session Routes
===============
POST /sessions  — Create a new interview session (with resume upload)
GET  /sessions/{id} — Get session details
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.database import MessageModel, SessionModel, get_db
from app.models.schemas import MessageResponse, SessionResponse
from app.services.resume_context import build_resume_context
from app.services.resume_parser import parse_resume

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", response_model=SessionResponse, status_code=201)
async def create_session(
    job_role: str = Form(...),
    job_description: str = Form(...),
    difficulty: str = Form(default="medium"),
    voice_mode: bool = Form(default=False),
    max_turns: int = Form(default=9),
    resume: Optional[UploadFile] = File(default=None),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new interview session.

    Accepts multipart form data with optional resume PDF.
    If a resume is provided, it's parsed and highlights are extracted.
    """
    settings = get_settings()

    # Validate difficulty
    if difficulty not in ("easy", "medium", "hard"):
        raise HTTPException(status_code=400, detail="difficulty must be 'easy', 'medium', or 'hard'")

    # Clamp max_turns
    max_turns = max(3, min(30, max_turns))

    # Parse resume if provided
    resume_text = ""
    resume_highlights = {"skills": [], "projects": [], "companies": [], "education": []}

    if resume:
        if not resume.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Resume must be a PDF file")

        pdf_bytes = await resume.read()
        if len(pdf_bytes) > 10 * 1024 * 1024:  # 10MB limit
            raise HTTPException(status_code=400, detail="Resume file too large (max 10MB)")

        try:
            parsed = await parse_resume(pdf_bytes)
            resume_text = parsed["raw_text"]
            resume_highlights = parsed["highlights"]
            logger.info(f"Resume parsed: {len(resume_text)} chars, {len(resume_highlights.get('skills', []))} skills")
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    # Create session in database
    resume_context = build_resume_context(resume_highlights, resume_text)
    session = SessionModel(
        job_role=job_role,
        job_description=job_description,
        resume_text=resume_text,
        resume_highlights=resume_highlights,
        resume_context=resume_context,
        voice_mode=voice_mode,
        difficulty=difficulty,
        max_turns=max_turns,
        turn_count=0,
        private_scores=[],
        status="active",
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    logger.info(f"Session created: {session.id} | role={job_role} | difficulty={difficulty}")

    return SessionResponse(
        session_id=session.id,
        status=session.status,
        job_role=session.job_role,
        difficulty=session.difficulty,
        max_turns=session.max_turns,
        voice_mode=session.voice_mode,
        created_at=session.created_at,
    )


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get session details by ID."""
    result = await db.execute(select(SessionModel).where(SessionModel.id == session_id))
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return SessionResponse(
        session_id=session.id,
        status=session.status,
        job_role=session.job_role,
        difficulty=session.difficulty,
        max_turns=session.max_turns,
        voice_mode=session.voice_mode,
        created_at=session.created_at,
    )


@router.get("/{session_id}/messages", response_model=list[MessageResponse])
async def get_messages(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get all messages for a session."""
    result = await db.execute(
        select(MessageModel)
        .where(MessageModel.session_id == session_id)
        .order_by(MessageModel.timestamp)
    )
    messages = result.scalars().all()

    return [
        MessageResponse(
            id=m.id,
            role=m.role,
            agent_name=m.agent_name,
            content=m.content,
            audio_url=m.audio_url,
            timestamp=m.timestamp,
        )
        for m in messages
    ]
