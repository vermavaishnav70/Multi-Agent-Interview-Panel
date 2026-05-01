"""
Transcription Route
====================
POST /sessions/{id}/transcribe — Audio blob → NVIDIA/Sarvam → transcript text
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.models.schemas import TranscriptResponse
from app.services.stt_service import transcribe_audio

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sessions", tags=["voice"])


@router.post("/{session_id}/transcribe", response_model=TranscriptResponse)
async def transcribe(
    session_id: str,
    audio: UploadFile = File(...),
):
    """
    Transcribe an audio recording using NVIDIA STT with Sarvam fallback.

    Accepts audio blob (webm, mp3, wav, etc.) and returns text transcript.
    The transcript can then be used as the user's answer input.
    """
    # Validate file
    if not audio.filename:
        raise HTTPException(status_code=400, detail="No audio file provided")

    audio_bytes = await audio.read()
    if len(audio_bytes) == 0:
        raise HTTPException(status_code=400, detail="Audio file is empty")
    if len(audio_bytes) > 25 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Audio file too large (max 25MB)")

    try:
        transcript = await transcribe_audio(audio_bytes, audio.filename)
        logger.info(f"Transcribed audio for session {session_id}: {len(transcript)} chars")
        return TranscriptResponse(transcript=transcript)
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
