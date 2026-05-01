from __future__ import annotations

import wave
from io import BytesIO

import pytest

from app.config import Settings
from app.services import stt_service


def _wav_bytes() -> bytes:
    buffer = BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(16000)
        wav_file.writeframes(b"\x00\x00" * 1600)
    return buffer.getvalue()


@pytest.mark.asyncio
async def test_stt_uses_nvidia_then_sarvam_then_elevenlabs(monkeypatch):
    settings = Settings(
        NIM_API_KEY="nim-key",
        NIM_STT_URL="grpc.nvcf.nvidia.com:443",
        NIM_STT_MODEL="openai/whisper-large-v3",
        SARVAM_API_KEY="sarvam-key",
        ELEVENLABS_API_KEY="elevenlabs-key",
    )
    calls: list[str] = []

    async def failing_nim(audio_bytes: bytes, filename: str) -> str:
        calls.append(f"nim:{filename}")
        raise RuntimeError("nim unavailable")

    async def failing_sarvam(audio_bytes: bytes, filename: str) -> str:
        calls.append(f"sarvam:{filename}")
        raise RuntimeError("sarvam unavailable")

    async def successful_elevenlabs(audio_bytes: bytes, filename: str) -> str:
        calls.append(f"elevenlabs:{filename}")
        return "hello from backup"

    monkeypatch.setattr(stt_service, "get_settings", lambda: settings)
    monkeypatch.setattr(stt_service, "_transcribe_nim", failing_nim)
    monkeypatch.setattr(stt_service, "_transcribe_sarvam", failing_sarvam)
    monkeypatch.setattr(stt_service, "_transcribe_elevenlabs", successful_elevenlabs)

    transcript = await stt_service.transcribe_audio(_wav_bytes(), "recording.wav")

    assert transcript == "hello from backup"
    assert calls == [
        "nim:recording.wav",
        "sarvam:recording.wav",
        "elevenlabs:recording.wav",
    ]


@pytest.mark.asyncio
async def test_stt_requires_any_configured_provider(monkeypatch):
    settings = Settings(
        NIM_API_KEY="",
        NIM_STT_URL="",
        NIM_STT_MODEL="",
        SARVAM_API_KEY="",
        ELEVENLABS_API_KEY="",
    )
    monkeypatch.setattr(stt_service, "get_settings", lambda: settings)

    with pytest.raises(ValueError, match="NVIDIA STT, Sarvam STT, or ElevenLabs STT"):
        await stt_service.transcribe_audio(_wav_bytes(), "recording.wav")
