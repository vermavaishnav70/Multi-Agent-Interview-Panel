from __future__ import annotations

import json
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select
from app.main import app
from app.models import database
from app.models.database import MessageModel, ScorecardModel, SessionModel


def _parse_sse_payload(payload: str) -> list[dict]:
    events: list[dict] = []
    for chunk in payload.split("\n\n"):
        if not chunk.startswith("data: "):
            continue
        events.append(json.loads(chunk[6:]))
    return events


@pytest.mark.asyncio
async def test_turn_endpoint_streams_and_persists_agent_message(monkeypatch, tmp_path: Path):
    database.configure_database(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    await database.init_db()
    session_id: str | None = None

    try:
        async with database.async_session_factory() as session:
            interview_session = SessionModel(
                job_role="Backend Engineer",
                job_description="Build reliable APIs and debug production incidents.",
                resume_text="Worked on APIs and queues.",
                resume_highlights={"skills": ["Python", "FastAPI"], "projects": [], "companies": [], "education": []},
                resume_context={"skills": ["Python", "FastAPI"], "projects": [], "companies": [], "education": [], "anchored_claims": [], "resume_excerpt": "Worked on APIs and queues."},
                voice_mode=True,
                max_turns=3,
                status="active",
                private_scores=[],
            )
            session.add(interview_session)
            await session.commit()
            await session.refresh(interview_session)
            session_id = interview_session.id

        class FakeRouter:
            async def generate_json(self, **kwargs):
                return {
                    "summary": "Good interview.",
                    "strengths": ["Clarity"],
                    "improvement_areas": ["Depth"],
                    "resume_accuracy": {"verified_claims": [], "unverified_claims": [], "inflated_claims": []},
                    "per_dimension_scores": {
                        "communication": 7,
                        "problem_solving": 7,
                        "technical_depth": 7,
                        "culture_fit": 7,
                    },
                    "final_score": 70,
                    "hire_recommendation": "yes",
                }

            async def stream_text(self, *, on_provider_switch=None, **kwargs):
                if on_provider_switch:
                    await on_provider_switch("nim", "gemini", "429 rate limit")
                for token in ["Tell ", "me ", "about a time you improved reliability."]:
                    yield token

        async def fake_tts(session_id: str, message_id: str, text: str, agent_role: str) -> str:
            return f"/api/sessions/{session_id}/messages/{message_id}/audio"

        monkeypatch.setattr("app.services.turn_service.get_provider_router", lambda: FakeRouter())
        monkeypatch.setattr("app.services.turn_service.synthesize_message_audio", fake_tts)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.post(
                f"/api/sessions/{session_id}/turn",
                json={"content": "", "idempotency_key": "opening-turn-1"},
            )

        assert response.status_code == 200
        events = _parse_sse_payload(response.text)
        event_types = [event["type"] for event in events]
        assert event_types[:4] == ["thinking", "agent_info", "provider_switch", "token"]
        assert "agent_done" in event_types
        assert "tts_ready" in event_types

        async with database.async_session_factory() as session:
            persisted = (
                await session.execute(select(MessageModel).where(MessageModel.session_id == session_id))
            ).scalars().all()
            assert len(persisted) == 1
            assert persisted[0].content == "Tell me about a time you improved reliability."
    finally:
        if session_id:
            async with database.async_session_factory() as session:
                await session.execute(delete(MessageModel).where(MessageModel.session_id == session_id))
                await session.execute(delete(ScorecardModel).where(ScorecardModel.session_id == session_id))
                await session.execute(delete(SessionModel).where(SessionModel.id == session_id))
                await session.commit()
