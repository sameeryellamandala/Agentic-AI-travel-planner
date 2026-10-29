"""Provider compatibility boundary for CrewAI's LiteLLM Groq integration."""

from crewai import LLM
from typing import Any
from pydantic import BaseModel


class GroqQuotaUnavailable(RuntimeError):
    """A provider quota cannot be resolved by silently waiting in the request."""


class GroqLLM(LLM):
    response_format: dict[str, Any] | type[BaseModel] | None = None

    def _handle_non_streaming_response(self, *args, **kwargs):
        unavailable = False
        try:
            return super()._handle_non_streaming_response(*args, **kwargs)
        except Exception as exc:
            message = str(exc).lower()
            headers = getattr(getattr(exc, "response", None), "headers", {}) or {}
            try:
                wait = float(headers.get("retry-after", 0))
            except (ValueError, TypeError):
                wait = 0
            unavailable = (
                "tokens per day" in message
                or "requests per day" in message
                or "request too large" in message
                or wait > 59
            )
            if not unavailable:
                raise
        # Outside the except block so CrewAI does not rediscover the throttling
        # exception through its error-chain classifier and wait for hours.
        if unavailable:
            raise GroqQuotaUnavailable(
                "Groq token allowance unavailable. Try a shorter trip or a model/account with available capacity."
            )

    def _format_messages_for_provider(self, messages):
        formatted = super()._format_messages_for_provider(messages)
        # CrewAI's prompt cache marker is not part of Groq's message schema.
        return [
            {
                key: value
                for key, value in message.items()
                if key not in ("cache_breakpoint", "cache_control")
            }
            for message in formatted
        ]
