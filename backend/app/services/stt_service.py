"""
STT Service — Speech to Text
==============================
Uses NVIDIA Whisper via Riva gRPC first, then Sarvam REST as backup.
"""

from __future__ import annotations

import io
import logging
import wave

import httpx
import riva.client

from app.config import get_settings

logger = logging.getLogger(__name__)


def _guess_mime_type(filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "wav"
    mime_map = {
        "wav": "audio/wav",
        "mp3": "audio/mpeg",
        "m4a": "audio/mp4",
        "mp4": "audio/mp4",
        "ogg": "audio/ogg",
        "opus": "audio/ogg",
        "webm": "audio/webm",
        "flac": "audio/flac",
    }
    return mime_map.get(ext, "application/octet-stream")


def _decode_wav_pcm(audio_bytes: bytes) -> tuple[bytes, int]:
    with wave.open(io.BytesIO(audio_bytes), "rb") as wav_file:
        channels = wav_file.getnchannels()
        sample_width = wav_file.getsampwidth()
        sample_rate = wav_file.getframerate()
        raw_audio = wav_file.readframes(wav_file.getnframes())

    if channels != 1:
        raise ValueError(f"NVIDIA STT expects mono WAV input, got {channels} channels")
    if sample_width != 2:
        raise ValueError(f"NVIDIA STT expects 16-bit WAV input, got {sample_width * 8}-bit")

    return raw_audio, sample_rate


def _build_nim_metadata() -> list[list[str]]:
    settings = get_settings()
    metadata = [["authorization", f"Bearer {settings.NIM_API_KEY}"]]
    if settings.NIM_STT_FUNCTION_ID:
        metadata.append(["function-id", settings.NIM_STT_FUNCTION_ID])
    return metadata


async def _transcribe_nim(audio_bytes: bytes, filename: str) -> str:
    settings = get_settings()
    if not settings.NIM_API_KEY or not settings.NIM_STT_URL or not settings.NIM_STT_MODEL:
        raise ValueError("NVIDIA STT is not configured")

    if not filename.lower().endswith(".wav"):
        raise ValueError("NVIDIA STT currently requires WAV input")

    raw_audio, sample_rate = _decode_wav_pcm(audio_bytes)
    auth = riva.client.Auth(
        uri=settings.NIM_STT_URL,
        use_ssl=True,
        metadata_args=_build_nim_metadata(),
    )
    asr = riva.client.ASRService(auth)
    config = riva.client.RecognitionConfig(
        encoding=riva.client.AudioEncoding.LINEAR_PCM,
        sample_rate_hertz=sample_rate,
        language_code=settings.NIM_STT_LANGUAGE,
        max_alternatives=1,
        enable_automatic_punctuation=True,
        model=settings.NIM_STT_MODEL,
    )
    response = asr.offline_recognize(raw_audio, config)
    transcript = " ".join(
        alt.transcript.strip()
        for result in response.results
        for alt in result.alternatives[:1]
        if alt.transcript.strip()
    ).strip()
    if not transcript:
        raise ValueError("NVIDIA STT returned an empty transcript")
    return transcript


async def _transcribe_sarvam(audio_bytes: bytes, filename: str) -> str:
    settings = get_settings()
    if not settings.SARVAM_API_KEY:
        raise ValueError("Sarvam STT is not configured")

    data = {
        "model": settings.SARVAM_STT_MODEL,
        "mode": settings.SARVAM_STT_MODE,
    }
    if settings.SARVAM_STT_LANGUAGE:
        data["language_code"] = settings.SARVAM_STT_LANGUAGE

    files = {
        "file": (filename, audio_bytes, _guess_mime_type(filename)),
    }

    async with httpx.AsyncClient(timeout=45.0) as client:
        response = await client.post(
            "https://api.sarvam.ai/speech-to-text",
            headers={"api-subscription-key": settings.SARVAM_API_KEY},
            data=data,
            files=files,
        )
        response.raise_for_status()
        payload = response.json()

    transcript = str(payload.get("transcript", "")).strip()
    if not transcript:
        raise ValueError("Sarvam STT returned an empty transcript")
    return transcript


async def _transcribe_elevenlabs(audio_bytes: bytes, filename: str) -> str:
    settings = get_settings()
    if not settings.ELEVENLABS_API_KEY:
        raise ValueError("ElevenLabs STT is not configured")

    files = {
        "file": (filename, audio_bytes, _guess_mime_type(filename)),
    }
    data = {
        "model_id": settings.ELEVENLABS_STT_MODEL,
    }

    async with httpx.AsyncClient(timeout=45.0) as client:
        response = await client.post(
            "https://api.elevenlabs.io/v1/speech-to-text",
            headers={"xi-api-key": settings.ELEVENLABS_API_KEY},
            data=data,
            files=files,
        )
        response.raise_for_status()
        payload = response.json()

    transcript = str(payload.get("text", "")).strip()
    if not transcript:
        raise ValueError("ElevenLabs STT returned an empty transcript")
    return transcript


async def transcribe_audio(audio_bytes: bytes, filename: str = "recording.wav") -> str:
    """
    Transcribe audio using NVIDIA Whisper first, then Sarvam, then ElevenLabs.
    """
    settings = get_settings()
    transcript: str | None = None

    if settings.NIM_API_KEY and settings.NIM_STT_URL and settings.NIM_STT_MODEL:
        try:
            transcript = await _transcribe_nim(audio_bytes, filename)
            logger.info("NVIDIA STT transcribed %s bytes -> %s chars", len(audio_bytes), len(transcript))
            return transcript
        except Exception as error:
            logger.warning("NVIDIA STT failed, falling back: %s", error)

    if settings.SARVAM_API_KEY:
        try:
            transcript = await _transcribe_sarvam(audio_bytes, filename)
            logger.info("Sarvam STT transcribed %s bytes -> %s chars", len(audio_bytes), len(transcript))
            return transcript
        except Exception as error:
            logger.warning("Sarvam STT failed: %s", error)

    if settings.ELEVENLABS_API_KEY:
        try:
            transcript = await _transcribe_elevenlabs(audio_bytes, filename)
            logger.info("ElevenLabs STT transcribed %s bytes -> %s chars", len(audio_bytes), len(transcript))
            return transcript
        except Exception as error:
            logger.warning("ElevenLabs STT failed: %s", error)

    raise ValueError("Voice transcription requires NVIDIA STT, Sarvam STT, or ElevenLabs STT to be configured")
