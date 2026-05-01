"""
Scorecard Route
================
GET /sessions/{id}/scorecard — Get the synthesizer's scorecard
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import ScorecardModel, SessionModel, get_db
from app.models.schemas import ResumeAccuracy, ScorecardResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sessions", tags=["scorecard"])


@router.get("/{session_id}/scorecard", response_model=ScorecardResponse)
async def get_scorecard(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get the interview scorecard for a completed session.

    Returns the synthesizer's evaluation including resume accuracy analysis.
    """
    # Check session exists and is completed
    session_result = await db.execute(
        select(SessionModel).where(SessionModel.id == session_id)
    )
    session = session_result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Session is not completed (status: {session.status}). Complete the interview first.",
        )

    # Fetch scorecard
    sc_result = await db.execute(
        select(ScorecardModel).where(ScorecardModel.session_id == session_id)
    )
    scorecard = sc_result.scalar_one_or_none()
    if not scorecard:
        raise HTTPException(status_code=404, detail="Scorecard not found for this session")

    scores = scorecard.scores_json or {}
    accuracy = scorecard.resume_accuracy or {}

    return ScorecardResponse(
        session_id=session_id,
        summary=scores.get("summary", "No summary available."),
        strengths=scores.get("strengths", []),
        improvement_areas=scores.get("improvement_areas", []),
        resume_accuracy=ResumeAccuracy(
            verified_claims=accuracy.get("verified_claims", []),
            unverified_claims=accuracy.get("unverified_claims", []),
            inflated_claims=accuracy.get("inflated_claims", []),
        ),
        per_dimension_scores=scores.get("per_dimension_scores", {}),
        final_score=scorecard.final_score or 0,
        hire_recommendation=scorecard.hire_recommendation or "borderline",
    )
