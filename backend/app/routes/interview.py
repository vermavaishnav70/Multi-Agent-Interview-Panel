"""
Unified interview turn and audio routes.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import get_db
from app.models.schemas import TurnRequest
from app.services.turn_service import stream_turn
from app.services.tts_service import audio_file_exists, get_audio_file_path, get_audio_media_type

router = APIRouter(prefix="/sessions", tags=["interview"])


@router.post("/{session_id}/turn")
async def turn(
    session_id: str,
    body: TurnRequest,
    db: AsyncSession = Depends(get_db),
):
    async def event_generator():
        async for event in stream_turn(
            db=db,
            session_id=session_id,
            content=body.content,
            transcribed_text=body.transcribed_text,
            idempotency_key=body.idempotency_key,
        ):
            yield event

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{session_id}/messages/{message_id}/audio")
async def get_message_audio(session_id: str, message_id: str):
    if not audio_file_exists(session_id, message_id):
        raise HTTPException(status_code=404, detail="Audio not found")

    return FileResponse(
        get_audio_file_path(session_id, message_id),
        media_type=get_audio_media_type(session_id, message_id),
        filename=get_audio_file_path(session_id, message_id).name,
    )
