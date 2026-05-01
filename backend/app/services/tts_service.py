"""
TTS generation and local audio storage.
"""

from __future__ import annotations

import base64
import io
import logging
import wave
from pathlib import Path

import httpx
import riva.client

from app.config import get_settings
from app.graph.voice_config import (
    AGENT_SPEEDS,
    ELEVENLABS_AGENT_VOICES,
    NVIDIA_AGENT_VOICES,
    SARVAM_AGENT_SPEAKERS,
)

logger = logging.getLogger(__name__)

_AUDIO_DIR = Path(__file__).resolve().parents[2] / "generated_audio"


def _audio_base_path(session_id: str, message_id: str) -> Path:
    return _AUDIO_DIR / session_id / message_id


def _audio_candidates(session_id: str, message_id: str) -> list[Path]:
    base = _audio_base_path(session_id, message_id)
    return [base.with_suffix(".mp3"), base.with_suffix(".wav")]


def _audio_path(session_id: str, message_id: str, suffix: str) -> Path:
    return _audio_base_path(session_id, message_id).with_suffix(suffix)


def get_audio_url(session_id: str, message_id: str) -> str:
    return f"/api/sessions/{session_id}/messages/{message_id}/audio"


def audio_file_exists(session_id: str, message_id: str) -> bool:
    return any(path.exists() for path in _audio_candidates(session_id, message_id))


def get_audio_file_path(session_id: str, message_id: str) -> Path:
    for path in _audio_candidates(session_id, message_id):
        if path.exists():
            return path
    return _audio_candidates(session_id, message_id)[0]


def get_audio_media_type(session_id: str, message_id: str) -> str:
    suffix = get_audio_file_path(session_id, message_id).suffix.lower()
    return "audio/wav" if suffix == ".wav" else "audio/mpeg"


def _build_nim_tts_metadata() -> list[list[str]]:
    settings = get_settings()
    metadata = [["authorization", f"Bearer {settings.NIM_API_KEY}"]]
    if settings.NIM_TTS_FUNCTION_ID:
        metadata.append(["function-id", settings.NIM_TTS_FUNCTION_ID])
    return metadata


def _wrap_pcm_as_wav(audio_bytes: bytes, sample_rate: int) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(audio_bytes)
    return buffer.getvalue()


async def _generate_sarvam_tts(text: str, agent_role: str) -> tuple[bytes, str]:
    settings = get_settings()
    speaker = SARVAM_AGENT_SPEAKERS.get(agent_role, SARVAM_AGENT_SPEAKERS["hr"])
    pace = AGENT_SPEEDS.get(agent_role, 1.0)
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            "https://api.sarvam.ai/text-to-speech",
            headers={
                "api-subscription-key": settings.SARVAM_API_KEY,
                "Content-Type": "application/json",
            },
            json={
                "text": text,
                "target_language_code": settings.SARVAM_TTS_LANGUAGE,
                "model": settings.SARVAM_TTS_MODEL,
                "speaker": speaker,
                "pace": pace,
                "output_audio_codec": settings.SARVAM_TTS_OUTPUT_CODEC,
                "temperature": 0.6,
            },
        )
        response.raise_for_status()
        payload = response.json()
        audio_items = payload.get("audios") or []
        if not audio_items:
            raise ValueError("Sarvam TTS response did not include audio")
        return base64.b64decode(audio_items[0]), ".mp3"


async def _generate_elevenlabs_tts(text: str, agent_role: str) -> tuple[bytes, str]:
    settings = get_settings()
    voice_id = ELEVENLABS_AGENT_VOICES.get(agent_role, ELEVENLABS_AGENT_VOICES["hr"])
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
            headers={
                "xi-api-key": settings.ELEVENLABS_API_KEY,
                "Content-Type": "application/json",
            },
            json={
                "text": text,
                "model_id": "eleven_flash_v2_5",
                "voice_settings": {"stability": 0.45, "similarity_boost": 0.75},
            },
        )
        response.raise_for_status()
        return response.content, ".mp3"


async def _generate_nim_tts_http(text: str, agent_role: str) -> tuple[bytes, str]:
    settings = get_settings()
    voice = NVIDIA_AGENT_VOICES.get(agent_role, "")
    speed = AGENT_SPEEDS.get(agent_role, 1.0)
    payload: dict[str, str | float] = {
        "model": settings.NIM_TTS_MODEL,
        "input": text,
        "speed": speed,
    }
    if voice:
        payload["voice"] = voice

    async with httpx.AsyncClient(timeout=45.0) as client:
        response = await client.post(
            settings.NIM_TTS_URL,
            headers={"Authorization": f"Bearer {settings.NIM_API_KEY}"},
            json=payload,
        )
        response.raise_for_status()
        return response.content, ".mp3"


async def _generate_nim_tts_riva(text: str, agent_role: str) -> tuple[bytes, str]:
    settings = get_settings()
    auth = riva.client.Auth(
        uri=settings.NIM_TTS_URL,
        use_ssl=True,
        metadata_args=_build_nim_tts_metadata(),
    )
    tts = riva.client.SpeechSynthesisService(auth)
    voice_name = NVIDIA_AGENT_VOICES.get(agent_role) or None
    prompt_file = Path(settings.NIM_TTS_PROMPT_FILE).expanduser() if settings.NIM_TTS_PROMPT_FILE else None
    response = tts.synthesize(
        text=text,
        voice_name=voice_name,
        language_code=settings.NIM_TTS_LANGUAGE,
        encoding=riva.client.AudioEncoding.LINEAR_PCM,
        sample_rate_hz=settings.NIM_TTS_SAMPLE_RATE,
        zero_shot_audio_prompt_file=prompt_file,
        audio_prompt_encoding=riva.client.AudioEncoding.LINEAR_PCM if prompt_file else riva.client.AudioEncoding.ENCODING_UNSPECIFIED,
        zero_shot_quality=settings.NIM_TTS_ZERO_SHOT_QUALITY,
        zero_shot_transcript=settings.NIM_TTS_PROMPT_TRANSCRIPT or None,
    )
    wav_bytes = _wrap_pcm_as_wav(response.audio, settings.NIM_TTS_SAMPLE_RATE)
    return wav_bytes, ".wav"


async def _generate_nim_tts(text: str, agent_role: str) -> tuple[bytes, str]:
    settings = get_settings()
    if not settings.NIM_TTS_URL or not settings.NIM_API_KEY or not settings.NIM_TTS_MODEL:
        raise ValueError("NIM TTS is not configured")

    if settings.NIM_TTS_URL.startswith("http://") or settings.NIM_TTS_URL.startswith("https://"):
        return await _generate_nim_tts_http(text, agent_role)

    return await _generate_nim_tts_riva(text, agent_role)


async def synthesize_message_audio(session_id: str, message_id: str, text: str, agent_role: str) -> str:
    """Generate audio for a message and return the API URL."""
    settings = get_settings()
    base_path = _audio_base_path(session_id, message_id)
    base_path.parent.mkdir(parents=True, exist_ok=True)

    audio_payload: tuple[bytes, str] | None = None

    if settings.NIM_TTS_URL and settings.NIM_API_KEY and settings.NIM_TTS_MODEL:
        try:
            audio_payload = await _generate_nim_tts(text, agent_role)
        except Exception as error:  # pragma: no cover - network-specific
            logger.warning("NIM TTS failed, falling back: %s", error)

    if audio_payload is None and settings.SARVAM_API_KEY:
        try:
            audio_payload = await _generate_sarvam_tts(text, agent_role)
        except Exception as error:  # pragma: no cover - network-specific
            logger.warning("Sarvam TTS failed: %s", error)

    if audio_payload is None and settings.ELEVENLABS_API_KEY:
        try:
            audio_payload = await _generate_elevenlabs_tts(text, agent_role)
        except Exception as error:  # pragma: no cover - network-specific
            logger.warning("ElevenLabs TTS failed: %s", error)

    if audio_payload is None:
        raise ValueError("Voice agents require NVIDIA NIM TTS, Sarvam TTS, or ElevenLabs TTS to be configured")

    audio_bytes, suffix = audio_payload
    for candidate in _audio_candidates(session_id, message_id):
        if candidate.exists():
            candidate.unlink()
    _audio_path(session_id, message_id, suffix).write_bytes(audio_bytes)
    return get_audio_url(session_id, message_id)
