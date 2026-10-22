"""OpenAI client wrapper used by all AI-powered features."""
import os
from openai import OpenAI, AsyncOpenAI
from openai import APITimeoutError as _SDKTimeoutError

_sync_client: OpenAI | None = None
_async_client: AsyncOpenAI | None = None

_NO_KEY_MSG = "Для функций ИИ задайте OPENAI_API_KEY в backend/.env."


class AITimeoutError(Exception):
    """Provider-agnostic timeout exception."""


class AINotConfiguredError(Exception):
    """Raised when the OpenAI API key is missing."""


def _check_key() -> None:
    if not os.getenv("OPENAI_API_KEY"):
        raise AINotConfiguredError(_NO_KEY_MSG)


def _sync() -> OpenAI:
    global _sync_client
    if _sync_client is None:
        _sync_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    return _sync_client


def _async() -> AsyncOpenAI:
    global _async_client
    if _async_client is None:
        _async_client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
    return _async_client


def _model() -> str:
    return os.getenv("OPENAI_MODEL", "gpt-4.1-mini")


def generate(prompt: str, *, max_tokens: int = 1024, timeout: float = 60.0) -> str:
    """Generate one response. Raises AITimeoutError on timeout."""
    _check_key()
    try:
        response = _sync().chat.completions.create(
            model=_model(),
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
            timeout=timeout,
        )
    except _SDKTimeoutError as exc:
        raise AITimeoutError("Запрос к OpenAI превысил время ожидания") from exc
    return (response.choices[0].message.content or "").strip()


async def stream_text(system: str, messages: list[dict], *, max_tokens: int = 1024):
    """Stream response text chunks from OpenAI."""
    _check_key()
    try:
        stream = await _async().chat.completions.create(
            model=_model(),
            max_tokens=max_tokens,
            stream=True,
            messages=[{"role": "system", "content": system}, *messages],
        )
        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta
    except _SDKTimeoutError as exc:
        raise AITimeoutError("Запрос к OpenAI превысил время ожидания") from exc
