from __future__ import annotations

from pathlib import Path

import pytest

from app.config import Settings
from app.services import tts_service


@pytest.mark.asyncio
async def test_tts_uses_nvidia_then_sarvam_then_elevenlabs(monkeypatch, tmp_path: Path):
    settings = Settings(
        NIM_API_KEY="nim-key",
        NIM_TTS_URL="https://nim.example.test/tts",
        NIM_TTS_MODEL="voice-model",
        SARVAM_API_KEY="sarvam-key",
        ELEVENLABS_API_KEY="elevenlabs-key",
    )
    calls: list[str] = []

    async def failing_nim(text: str, agent_role: str) -> tuple[bytes, str]:
        calls.append(f"nim:{agent_role}:{text}")
        raise RuntimeError("nim unavailable")

    async def failing_sarvam(text: str, agent_role: str) -> tuple[bytes, str]:
        calls.append(f"sarvam:{agent_role}:{text}")
        raise RuntimeError("sarvam unavailable")

    async def successful_elevenlabs(text: str, agent_role: str) -> tuple[bytes, str]:
        calls.append(f"elevenlabs:{agent_role}:{text}")
        return b"mp3-bytes", ".mp3"

    monkeypatch.setattr(tts_service, "get_settings", lambda: settings)
    monkeypatch.setattr(tts_service, "_AUDIO_DIR", tmp_path)
    monkeypatch.setattr(tts_service, "_generate_nim_tts", failing_nim)
    monkeypatch.setattr(tts_service, "_generate_sarvam_tts", failing_sarvam)
    monkeypatch.setattr(tts_service, "_generate_elevenlabs_tts", successful_elevenlabs)

    audio_url = await tts_service.synthesize_message_audio("session-1", "message-1", "Hello", "technical")

    assert audio_url == "/api/sessions/session-1/messages/message-1/audio"
    assert calls == [
        "nim:technical:Hello",
        "sarvam:technical:Hello",
        "elevenlabs:technical:Hello",
    ]
    assert (tmp_path / "session-1" / "message-1.mp3").read_bytes() == b"mp3-bytes"


@pytest.mark.asyncio
async def test_tts_requires_any_configured_provider(monkeypatch, tmp_path: Path):
    settings = Settings(
        NIM_API_KEY="",
        NIM_TTS_URL="",
        NIM_TTS_MODEL="",
        SARVAM_API_KEY="",
        ELEVENLABS_API_KEY="",
    )

    monkeypatch.setattr(tts_service, "get_settings", lambda: settings)
    monkeypatch.setattr(tts_service, "_AUDIO_DIR", tmp_path)

    with pytest.raises(ValueError, match="NVIDIA NIM TTS, Sarvam TTS, or ElevenLabs TTS"):
        await tts_service.synthesize_message_audio("session-1", "message-1", "Hello", "hr")
