from types import SimpleNamespace

import pytest

from app.services.provider_router import ProviderRouter


@pytest.mark.asyncio
async def test_provider_router_retries_and_falls_back():
    settings = SimpleNamespace(
        NIM_API_KEY="nim-key",
        NIM_BASE_URL="https://nim.example/v1",
        NIM_FAST_MODEL="nim-fast",
        NIM_STRONG_MODEL="nim-strong",
        GOOGLE_API_KEY="google-key",
        GEMINI_FAST_MODEL="gemini-fast",
        GEMINI_STRONG_MODEL="gemini-strong",
        GROQ_API_KEY="groq-key",
        GROQ_FAST_MODEL="groq-fast",
        GROQ_STRONG_MODEL="groq-strong",
    )
    router = ProviderRouter(settings=settings)
    attempts: list[str] = []
    switches: list[tuple[str, str, str]] = []

    async def fake_invoke(provider, system_prompt, user_prompt, temperature):
        attempts.append(provider.name)
        if provider.name == "nim":
            raise RuntimeError("429 rate limit exceeded")
        return "ok"

    async def on_switch(from_provider: str, to_provider: str, reason: str) -> None:
        switches.append((from_provider, to_provider, reason))

    router._invoke_text = fake_invoke  # type: ignore[method-assign]

    result = await router.generate_text(
        system_prompt="system",
        user_prompt="user",
        tier="fast",
        on_provider_switch=on_switch,
    )

    assert result == "ok"
    assert attempts == ["nim", "nim", "gemini"]
    assert switches[0][0] == "nim"
    assert switches[0][1] == "gemini"
