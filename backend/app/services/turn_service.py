"""
Unified turn orchestration for the V1 interview flow.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncGenerator

from fastapi import HTTPException
from langchain_core.messages import AIMessage, HumanMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.graph.evaluator import build_evaluator_prompt
from app.graph.interviewer import build_question_prompt
from app.graph.prompts import (
    AGENT_DIMENSIONS,
    SYNTHESIZER_PROMPT,
    format_private_scores,
    format_recent_transcript,
    format_resume_context,
)
from app.graph.supervisor import supervisor_route
from app.models.database import MessageModel, ScorecardModel, SessionModel
from app.models.state import SessionState
from app.services.provider_router import get_provider_router
from app.services.tts_service import synthesize_message_audio


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


async def _load_session(db: AsyncSession, session_id: str) -> SessionModel:
    result = await db.execute(select(SessionModel).where(SessionModel.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


async def _load_messages(db: AsyncSession, session_id: str) -> list[MessageModel]:
    result = await db.execute(
        select(MessageModel).where(MessageModel.session_id == session_id).order_by(MessageModel.timestamp)
    )
    return list(result.scalars().all())


def _state_from_session(session: SessionModel, messages: list[MessageModel]) -> SessionState:
    lc_messages = []
    for message in messages:
        if message.role == "user":
            lc_messages.append(HumanMessage(content=message.content))
        else:
            lc_messages.append(AIMessage(content=message.content, name=message.agent_name or "agent"))

    asked_questions = sum(1 for message in messages if message.role == "agent" and message.agent_name != "synthesizer")
    agent_history = [message.agent_name for message in messages if message.agent_name and message.agent_name != "synthesizer"]

    return {
        "session_id": session.id,
        "job_role": session.job_role,
        "job_description": session.job_description,
        "resume_text": session.resume_text or "",
        "resume_highlights": session.resume_highlights or {},
        "resume_context": session.resume_context or {},
        "turn_count": session.turn_count,
        "asked_questions": asked_questions,
        "max_turns": session.max_turns,
        "messages": lc_messages,
        "current_agent": "",
        "agent_history": agent_history,
        "difficulty": session.difficulty,
        "private_scores": list(session.private_scores or []),
        "status": session.status,
        "scorecard": None,
        "voice_mode": session.voice_mode,
        "latest_agent_response": "",
        "last_resume_reference": None,
    }


async def _evaluate_latest_answer(
    *,
    state: SessionState,
    messages: list[MessageModel],
) -> list[dict]:
    last_user = next((message for message in reversed(messages) if message.role == "user"), None)
    last_agent = next(
        (
            message
            for message in reversed(messages)
            if message.role == "agent" and message.agent_name in AGENT_DIMENSIONS
        ),
        None,
    )

    if not last_user or not last_agent:
        return list(state.get("private_scores", []))

    router = get_provider_router()
    system_prompt, user_prompt = build_evaluator_prompt(
        agent_name=last_agent.agent_name or "hr",
        previous_question=last_agent.content,
        latest_answer=last_user.content,
        resume_context=state.get("resume_context", {}),
        difficulty=state["difficulty"],
    )
    result = await router.generate_json(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        tier="fast",
        temperature=0.2,
    )
    entry = {
        "agent": last_agent.agent_name,
        "dimension": result.get("dimension", AGENT_DIMENSIONS.get(last_agent.agent_name or "hr", "culture_fit")),
        "score": max(0, min(10, int(result.get("score", 5)))),
        "reasoning": str(result.get("reasoning", "")).strip()[:400],
        "resume_reference": result.get("resume_reference"),
    }
    return [*state.get("private_scores", []), entry]


async def _build_scorecard(state: SessionState, on_provider_switch=None) -> dict:
    router = get_provider_router()
    transcript = format_recent_transcript(state.get("messages", []), last_n=100)
    user_prompt = f"""=== COMPACT RESUME CONTEXT ===
{format_resume_context(state.get("resume_context", {}))}

=== FULL TRANSCRIPT ===
{transcript}

=== EVALUATOR SCORES ===
{format_private_scores(state.get("private_scores", []))}

=== JOB ROLE ===
{state.get("job_role", "")}
"""
    result = await router.generate_json(
        system_prompt=SYNTHESIZER_PROMPT,
        user_prompt=user_prompt,
        tier="strong",
        temperature=0.2,
        on_provider_switch=on_provider_switch,
    )

    valid_recommendations = {"strong_yes", "yes", "borderline", "no"}
    recommendation = result.get("hire_recommendation", "borderline")
    if recommendation not in valid_recommendations:
        recommendation = "borderline"

    per_dimension = result.get("per_dimension_scores", {}) or {}
    normalized_dimensions = {
        "communication": max(0, min(10, int(per_dimension.get("communication", 5)))),
        "problem_solving": max(0, min(10, int(per_dimension.get("problem_solving", 5)))),
        "technical_depth": max(0, min(10, int(per_dimension.get("technical_depth", 5)))),
        "culture_fit": max(0, min(10, int(per_dimension.get("culture_fit", 5)))),
    }

    return {
        "summary": str(result.get("summary", "")).strip(),
        "strengths": [str(item).strip() for item in result.get("strengths", [])[:3]],
        "improvement_areas": [str(item).strip() for item in result.get("improvement_areas", [])[:3]],
        "resume_accuracy": {
            "verified_claims": [str(item).strip() for item in result.get("resume_accuracy", {}).get("verified_claims", [])[:5]],
            "unverified_claims": [str(item).strip() for item in result.get("resume_accuracy", {}).get("unverified_claims", [])[:5]],
            "inflated_claims": [str(item).strip() for item in result.get("resume_accuracy", {}).get("inflated_claims", [])[:5]],
        },
        "per_dimension_scores": normalized_dimensions,
        "final_score": max(0, min(100, int(result.get("final_score", 50)))),
        "hire_recommendation": recommendation,
    }


async def stream_turn(
    *,
    db: AsyncSession,
    session_id: str,
    content: str,
    transcribed_text: str | None = None,
    idempotency_key: str | None = None,
) -> AsyncGenerator[str, None]:
    _ = idempotency_key
    session = await _load_session(db, session_id)
    if session.status == "completed":
        yield _sse({"type": "error", "message": "Interview is already completed"})
        return

    normalized_content = (transcribed_text if transcribed_text is not None else content).strip()

    if normalized_content:
        user_message = MessageModel(
            session_id=session_id,
            role="user",
            content=normalized_content,
        )
        db.add(user_message)
        session.turn_count += 1
        await db.commit()

    messages = await _load_messages(db, session_id)
    state = _state_from_session(session, messages)

    if normalized_content:
        session.private_scores = await _evaluate_latest_answer(state=state, messages=messages)
        state["private_scores"] = list(session.private_scores or [])
        await db.commit()

    yield _sse({"type": "thinking", "message": "Preparing next interviewer..."})

    next_node = supervisor_route(state)
    if next_node == "synthesizer":
        async def on_provider_switch(from_provider: str, to_provider: str, reason: str) -> None:
            nonlocal pending_switch_events
            pending_switch_events.append(
                _sse(
                    {
                        "type": "provider_switch",
                        "from_provider": from_provider,
                        "to_provider": to_provider,
                        "reason": reason,
                    }
                )
            )

        pending_switch_events: list[str] = []
        scorecard = await _build_scorecard(state, on_provider_switch=on_provider_switch)
        for event in pending_switch_events:
            yield event

        scorecard_row = ScorecardModel(
            session_id=session_id,
            scores_json=scorecard,
            resume_accuracy=scorecard["resume_accuracy"],
            final_score=scorecard["final_score"],
            hire_recommendation=scorecard["hire_recommendation"],
        )
        db.add(scorecard_row)
        session.status = "completed"
        await db.commit()
        yield _sse({"type": "session_complete", "scorecard_ready": True})
        return

    state["current_agent"] = next_node
    question_system_prompt = build_question_prompt(next_node, state)
    question_user_prompt = "Write the next interview question."

    yield _sse(
        {
            "type": "agent_info",
            "agent": next_node,
            "turn_count": session.turn_count,
            "max_turns": session.max_turns,
        }
    )

    router = get_provider_router()
    response_text_parts: list[str] = []
    pending_switch_events: list[str] = []

    async def on_provider_switch(from_provider: str, to_provider: str, reason: str) -> None:
        pending_switch_events.append(
            _sse(
                {
                    "type": "provider_switch",
                    "from_provider": from_provider,
                    "to_provider": to_provider,
                    "reason": reason,
                }
            )
        )

    for event in pending_switch_events:
        yield event

    async for token in router.stream_text(
        system_prompt=question_system_prompt,
        user_prompt=question_user_prompt,
        tier="fast",
        temperature=0.55,
        on_provider_switch=on_provider_switch,
    ):
        while pending_switch_events:
            yield pending_switch_events.pop(0)
        response_text_parts.append(token)
        yield _sse({"type": "token", "agent": next_node, "content": token})

    final_text = "".join(response_text_parts).strip()
    if not final_text:
        final_text = "Can you tell me more about that?"

    message_id = uuid.uuid4().hex
    agent_message = MessageModel(
        id=message_id,
        session_id=session_id,
        role="agent",
        agent_name=next_node,
        content=final_text,
    )
    db.add(agent_message)
    await db.commit()

    yield _sse({"type": "agent_done", "agent": next_node, "message_id": message_id})

    if session.voice_mode and next_node != "synthesizer":
        try:
            audio_url = await synthesize_message_audio(session_id, message_id, final_text, next_node)
        except Exception as error:
            logger.warning("TTS generation failed for message %s: %s", message_id, error)
            yield _sse({"type": "error", "message": str(error)})
            return
        agent_message.audio_url = audio_url
        await db.commit()
        yield _sse({"type": "tts_ready", "agent": next_node, "message_id": message_id, "audio_url": audio_url})
