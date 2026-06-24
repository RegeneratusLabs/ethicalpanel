"""Tests for llm.LLMClient.

We mock the anthropic SDK so no real network call happens. The client
must parse the first JSON object from the response text, retry once on
transient errors, and raise `LLMError` on anything else.
"""
import pytest
from unittest.mock import MagicMock, patch

from ethics_canvas.llm import LLMClient, LLMError


def _mock_message(text: str) -> MagicMock:
    msg = MagicMock()
    msg.content = [MagicMock(text=text)]
    return msg


def test_evaluate_parses_json_object():
    with patch("ethics_canvas.llm.anthropic.Anthropic") as MockAnthropic:
        client_instance = MockAnthropic.return_value
        client_instance.messages.create.return_value = _mock_message(
            '{"score": 80, "flags": []}'
        )
        client = LLMClient(api_key="sk-x", base_url="https://x", model="m", timeout=10)
        out = client.evaluate("prompt", system="sys")
        assert out == {"score": 80, "flags": []}
        client_instance.messages.create.assert_called_once()
        call_kwargs = client_instance.messages.create.call_args.kwargs
        assert call_kwargs["model"] == "m"
        assert call_kwargs["max_tokens"] == 4096
        assert call_kwargs["system"] == "sys"


def test_evaluate_extracts_json_from_preamble():
    with patch("ethics_canvas.llm.anthropic.Anthropic") as MockAnthropic:
        client_instance = MockAnthropic.return_value
        client_instance.messages.create.return_value = _mock_message(
            'Here is the result:\n```json\n{"score": 42}\n```'
        )
        client = LLMClient(api_key="sk-x", base_url="https://x", model="m", timeout=10)
        out = client.evaluate("prompt")
        assert out == {"score": 42}


def test_evaluate_raises_llm_error_on_malformed_json():
    with patch("ethics_canvas.llm.anthropic.Anthropic") as MockAnthropic:
        client_instance = MockAnthropic.return_value
        client_instance.messages.create.return_value = _mock_message("not json at all")
        client = LLMClient(api_key="sk-x", base_url="https://x", model="m", timeout=10)
        with pytest.raises(LLMError) as exc:
            client.evaluate("prompt")
        assert exc.value.status is None
        assert "json" in exc.value.message.lower() or "parse" in exc.value.message.lower() or "no json" in exc.value.message.lower()


def test_evaluate_retries_once_on_5xx():
    import anthropic
    with patch("ethics_canvas.llm.anthropic.Anthropic") as MockAnthropic:
        client_instance = MockAnthropic.return_value
        # First call: 5xx InternalServerError, Second call: success
        client_instance.messages.create.side_effect = [
            anthropic.InternalServerError(
                message="boom",
                response=MagicMock(),
                body=None,
            ),
            _mock_message('{"ok": true}'),
        ]
        client = LLMClient(api_key="sk-x", base_url="https://x", model="m", timeout=10)
        out = client.evaluate("prompt")
        assert out == {"ok": True}
        assert client_instance.messages.create.call_count == 2


def test_evaluate_does_not_retry_on_4xx():
    import anthropic
    with patch("ethics_canvas.llm.anthropic.Anthropic") as MockAnthropic:
        client_instance = MockAnthropic.return_value
        fake_response = MagicMock()
        fake_response.status_code = 401
        client_instance.messages.create.side_effect = anthropic.AuthenticationError(
            message="bad key",
            response=fake_response,
            body=None,
        )
        client = LLMClient(api_key="sk-x", base_url="https://x", model="m", timeout=10)
        with pytest.raises(LLMError) as exc:
            client.evaluate("prompt")
        assert exc.value.status == 401
        assert client_instance.messages.create.call_count == 1


@pytest.mark.asyncio
async def test_evaluate_stream_yields_chunks_in_order():
    """evaluate_stream should yield text deltas in arrival order."""
    from unittest.mock import AsyncMock

    client = LLMClient(
        api_key="sk-test",
        base_url="https://example.com",
        model="test-model",
        timeout=30,
    )

    mock_stream = MagicMock()
    async def fake_text_stream():
        for chunk in ["Hello, ", "world", "!"]:
            yield chunk
    mock_stream.text_stream = fake_text_stream()

    mock_async_client = MagicMock()
    mock_async_client.messages.stream.return_value.__aenter__ = AsyncMock(return_value=mock_stream)
    mock_async_client.messages.stream.return_value.__aexit__ = AsyncMock(return_value=None)
    client._async_client = mock_async_client

    chunks = []
    async for chunk in client.evaluate_stream("test prompt", system="sys"):
        chunks.append(chunk)

    assert chunks == ["Hello, ", "world", "!"]
    mock_async_client.messages.stream.assert_called_once()
    call_kwargs = mock_async_client.messages.stream.call_args.kwargs
    assert call_kwargs["model"] == "test-model"
    assert call_kwargs["max_tokens"] == 4096
    assert call_kwargs["system"] == "sys"
