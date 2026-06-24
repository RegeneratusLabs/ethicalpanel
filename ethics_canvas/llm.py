"""Thin wrapper around the Anthropic SDK, pointed at DeepSeek's
Anthropic-compatible endpoint.

Hard-fail philosophy: any error (auth, rate limit, network, malformed
JSON, missing schema fields) becomes a structured `LLMError`. Transient
errors (5xx, connection error, timeout) are retried exactly once with
a 1-second backoff.
"""
from __future__ import annotations
import json
import logging
import time
from typing import Any

import anthropic


log = logging.getLogger("ethics_canvas.llm")


class LLMError(Exception):
    """Raised for any LLM failure. `status` is None for non-HTTP errors."""

    def __init__(self, status: int | None, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


# Transient HTTP statuses and SDK exception types that warrant one retry.
_RETRY_EXCEPTIONS: tuple[type[Exception], ...] = (
    anthropic.InternalServerError,
    anthropic.APITimeoutError,
    anthropic.APIConnectionError,
)


def _extract_first_json_object(text: str) -> dict[str, Any]:
    """Find and parse the first balanced `{...}` JSON object in `text`."""
    decoder = json.JSONDecoder()
    for i, ch in enumerate(text):
        if ch != "{":
            continue
        try:
            obj, _end = decoder.raw_decode(text[i:])
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            continue
    raise LLMError(None, f"no JSON object found in LLM response: {text[:200]!r}")


class LLMClient:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout: int,
        thinking: dict | None = None,
    ) -> None:
        self._model = model
        self._thinking = thinking
        self._client = anthropic.Anthropic(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
        )
        self._async_client = anthropic.AsyncAnthropic(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
        )

    def evaluate(self, prompt: str, system: str | None = None) -> dict[str, Any]:
        """Send `prompt` to the LLM and return the parsed JSON object.

        Retries once on transient failures. Raises `LLMError` on any
        other failure (auth, rate limit, malformed JSON, etc.).
        """
        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system is not None:
            kwargs["system"] = system

        attempt = 0
        last_exc: Exception | None = None
        while attempt < 2:
            try:
                start = time.monotonic()
                resp = self._client.messages.create(**kwargs)
                latency_ms = int((time.monotonic() - start) * 1000)
                text = next(b.text for b in resp.content if hasattr(b, "text"))
                log.info("llm ok latency_ms=%d", latency_ms)
                return _extract_first_json_object(text)
            except _RETRY_EXCEPTIONS as e:
                last_exc = e
                attempt += 1
                log.warning("llm transient error attempt=%d err=%r", attempt, e)
                if attempt < 2:
                    time.sleep(1.0)
                continue
            except anthropic.APIStatusError as e:
                # Non-retryable HTTP error (4xx etc).
                raise LLMError(e.status_code, f"LLM API error: {e.message}") from e
            except anthropic.APIError as e:
                # Catch-all for any other SDK error.
                raise LLMError(None, f"LLM SDK error: {e}") from e

        # Both attempts failed with transient errors.
        raise LLMError(
            None, f"LLM request failed after retry: {last_exc!r}"
        ) from last_exc

    async def evaluate_stream(
        self, prompt: str, system: str | None = None
    ) -> "typing.AsyncIterator[str]":
        """Stream text chunks from the LLM.

        Yields text deltas in arrival order. The caller is responsible
        for parsing structure out of the accumulated text.
        """
        import typing

        kwargs: dict[str, typing.Any] = {
            "model": self._model,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system is not None:
            kwargs["system"] = system
        if self._thinking is not None:
            kwargs["thinking"] = self._thinking

        async with self._async_client.messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                yield text
