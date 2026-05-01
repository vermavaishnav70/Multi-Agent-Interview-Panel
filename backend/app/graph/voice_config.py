"""
Voice Configuration
====================
Maps each agent role to provider-specific voice settings,
creating the illusion of a multi-person interview panel.
"""

# NVIDIA TTS voice names vary by enabled model/endpoint. Override these in
# the NIM service if your endpoint requires a specific catalog.
NVIDIA_AGENT_VOICES: dict[str, str] = {
    "hr": "",
    "technical": "",
    "behavioral": "",
    "synthesizer": "",
}

SARVAM_AGENT_SPEAKERS: dict[str, str] = {
    "hr": "shreya",
    "technical": "shubh",
    "behavioral": "ishita",
    "synthesizer": "manan",
}

ELEVENLABS_AGENT_VOICES: dict[str, str] = {
    "hr": "21m00Tcm4TlvDq8ikWAM",
    "technical": "ErXwobaYiN019PkySvjV",
    "behavioral": "EXAVITQu4vr4xnSDxMaL",
    "synthesizer": "VR6AewLTigWG4xSOukaG",
}

AGENT_SPEEDS: dict[str, float] = {
    "hr": 0.95,
    "technical": 1.0,
    "behavioral": 0.9,
    "synthesizer": 0.9,
}

# Display names for the frontend
AGENT_DISPLAY_NAMES: dict[str, str] = {
    "hr": "HR Interviewer",
    "technical": "Technical Lead",
    "behavioral": "Behavioral Coach",
    "synthesizer": "Panel Synthesizer",
}

# Accent colors for frontend styling (CSS custom properties)
AGENT_COLORS: dict[str, str] = {
    "hr": "#10b981",         # Emerald
    "technical": "#06b6d4",   # Cyan
    "behavioral": "#f59e0b",  # Amber
    "synthesizer": "#8b5cf6", # Violet
}
