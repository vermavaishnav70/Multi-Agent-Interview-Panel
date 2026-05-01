"""
Centralized LLM provider routing with retry and fallback support.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Awaitable, Callable

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from openai import AsyncOpenAI

from app.config import Settings, get_settings


ProviderSwitchHandler = Callable[[str, str, str], Awaitable[None] | None]


@dataclass(frozen=True)
class ProviderSpec:
    name: str
    model: str


def _strip_code_fences(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1].rsplit("```", 1)[0]
    return cleaned.strip()


def _is_retryable_error(error: Exception) -> bool:
    message = str(error).lower()
    retryable_markers = [
        "429",
        "rate limit",
        "resource exhausted",
        "quota",
        "timeout",
        "timed out",
        "deadline exceeded",
        "temporarily unavailable",
        "connection reset",
    ]
    return any(marker in message for marker in retryable_markers)


class ProviderRouter:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def _provider_chain(self, tier: str) -> list[ProviderSpec]:
        chain: list[ProviderSpec] = []
        if self.settings.NIM_API_KEY:
            chain.append(
                ProviderSpec(
                    name="nim",
                    model=self.settings.NIM_STRONG_MODEL if tier == "strong" else self.settings.NIM_FAST_MODEL,
                )
            )
        if self.settings.GOOGLE_API_KEY:
            chain.append(
                ProviderSpec(
                    name="gemini",
                    model=(
                        self.settings.GEMINI_STRONG_MODEL
                        if tier == "strong"
                        else self.settings.GEMINI_FAST_MODEL
                    ),
                )
            )
        if self.settings.GROQ_API_KEY:
            chain.append(
                ProviderSpec(
                    name="groq",
                    model=self.settings.GROQ_STRONG_MODEL if tier == "strong" else self.settings.GROQ_FAST_MODEL,
                )
            )
        if not chain:
            raise ValueError("No LLM providers configured. Add NIM_API_KEY, GOOGLE_API_KEY, or GROQ_API_KEY.")
        return chain

    async def generate_text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        tier: str = "fast",
        temperature: float = 0.3,
        on_provider_switch: ProviderSwitchHandler = None,
    ) -> str:
        return await self._run_with_fallback(
            tier=tier,
            on_provider_switch=on_provider_switch,
            runner=lambda provider: self._invoke_text(provider, system_prompt, user_prompt, temperature),
        )

    async def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        tier: str = "fast",
        temperature: float = 0.2,
        on_provider_switch: ProviderSwitchHandler = None,
    ) -> dict:
        text = await self.generate_text(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            tier=tier,
            temperature=temperature,
            on_provider_switch=on_provider_switch,
        )
        return json.loads(_strip_code_fences(text))

    async def stream_text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        tier: str = "fast",
        temperature: float = 0.5,
        on_provider_switch: ProviderSwitchHandler = None,
    ):
        providers = self._provider_chain(tier)
        last_error: Exception | None = None

        for index, provider in enumerate(providers):
            if index > 0 and on_provider_switch:
                previous = providers[index - 1]
                maybe_awaitable = on_provider_switch(previous.name, provider.name, str(last_error or "fallback"))
                if asyncio.iscoroutine(maybe_awaitable):
                    await maybe_awaitable

            for attempt in range(2):
                try:
                    async for token in self._stream_from_provider(
                        provider,
                        system_prompt,
                        user_prompt,
                        temperature,
                    ):
                        yield token
                    return
                except Exception as error:  # pragma: no cover - network-specific branches
                    last_error = error
                    if attempt == 0 and _is_retryable_error(error):
                        await asyncio.sleep(0.35)
                        continue
                    break

        raise last_error or RuntimeError("Provider routing failed")

    async def _run_with_fallback(
        self,
        *,
        tier: str,
        on_provider_switch: ProviderSwitchHandler,
        runner: Callable[[ProviderSpec], Awaitable[str]],
    ) -> str:
        providers = self._provider_chain(tier)
        last_error: Exception | None = None

        for index, provider in enumerate(providers):
            if index > 0 and on_provider_switch:
                previous = providers[index - 1]
                maybe_awaitable = on_provider_switch(previous.name, provider.name, str(last_error or "fallback"))
                if asyncio.iscoroutine(maybe_awaitable):
                    await maybe_awaitable

            for attempt in range(2):
                try:
                    return await runner(provider)
                except Exception as error:  # pragma: no cover - network-specific branches
                    last_error = error
                    if attempt == 0 and _is_retryable_error(error):
                        await asyncio.sleep(0.35)
                        continue
                    break

        raise last_error or RuntimeError("Provider routing failed")

    async def _invoke_text(
        self,
        provider: ProviderSpec,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
    ) -> str:
        if provider.name == "nim":
            return await self._invoke_openai_compatible(
                base_url=self.settings.NIM_BASE_URL,
                api_key=self.settings.NIM_API_KEY,
                model=provider.model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
            )
        if provider.name == "groq":
            return await self._invoke_openai_compatible(
                base_url="https://api.groq.com/openai/v1",
                api_key=self.settings.GROQ_API_KEY,
                model=provider.model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
            )
        if provider.name == "gemini":
            return await self._invoke_gemini(provider.model, system_prompt, user_prompt, temperature)
        raise ValueError(f"Unsupported provider: {provider.name}")

    async def _stream_from_provider(
        self,
        provider: ProviderSpec,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
    ):
        if provider.name == "nim":
            async for token in self._stream_openai_compatible(
                base_url=self.settings.NIM_BASE_URL,
                api_key=self.settings.NIM_API_KEY,
                model=provider.model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
            ):
                yield token
            return

        if provider.name == "groq":
            async for token in self._stream_openai_compatible(
                base_url="https://api.groq.com/openai/v1",
                api_key=self.settings.GROQ_API_KEY,
                model=provider.model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
            ):
                yield token
            return

        if provider.name == "gemini":
            async for token in self._stream_gemini(provider.model, system_prompt, user_prompt, temperature):
                yield token
            return

        raise ValueError(f"Unsupported provider: {provider.name}")

    async def _invoke_openai_compatible(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
    ) -> str:
        client = AsyncOpenAI(base_url=base_url, api_key=api_key, max_retries=0)
        response = await client.chat.completions.create(
            model=model,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.choices[0].message.content or ""

    async def _stream_openai_compatible(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
    ):
        client = AsyncOpenAI(base_url=base_url, api_key=api_key, max_retries=0)
        stream = await client.chat.completions.create(
            model=model,
            temperature=temperature,
            stream=True,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )

        async for chunk in stream:
            token = chunk.choices[0].delta.content or ""
            if token:
                yield token

    async def _invoke_gemini(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
    ) -> str:
        llm = ChatGoogleGenerativeAI(
            model=model,
            google_api_key=self.settings.GOOGLE_API_KEY,
            temperature=temperature,
            convert_system_message_to_human=True,
            max_retries=0,
        )
        response = await llm.ainvoke([SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)])
        content = response.content
        return content if isinstance(content, str) else "".join(str(part) for part in content)

    async def _stream_gemini(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
    ):
        llm = ChatGoogleGenerativeAI(
            model=model,
            google_api_key=self.settings.GOOGLE_API_KEY,
            temperature=temperature,
            convert_system_message_to_human=True,
            max_retries=0,
        )
        async for chunk in llm.astream([SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]):
            content = chunk.content
            token = content if isinstance(content, str) else "".join(str(part) for part in content)
            if token:
                yield token


_provider_router: ProviderRouter | None = None


def get_provider_router() -> ProviderRouter:
    global _provider_router
    if _provider_router is None:
        _provider_router = ProviderRouter()
    return _provider_router
