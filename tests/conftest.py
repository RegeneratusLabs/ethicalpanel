"""Shared pytest fixtures."""
import pytest
from unittest.mock import MagicMock, AsyncMock

from fastapi.testclient import TestClient

from ethics_canvas.api import app
from ethics_canvas.config import Settings
from ethics_canvas.llm import LLMClient


@pytest.fixture
def fake_settings() -> Settings:
    return Settings(_env_file=None, deepseek_api_key="sk-test-fixture")


@pytest.fixture
def fake_streaming_llm():
    """A mock LLMClient whose evaluate_stream yields one chunk per character
    to simulate real token-by-token streaming from the LLM."""
    from ethics_canvas.evaluator import AGENT_ORDER
    reasoning_by_id = {
        "steward":     "Footprint concerns are present but manageable.",
        "advocate":    "Distribution of outcomes looks equitable.",
        "beacon":      "Disclosure cadence needs sharper definition.",
        "custodian":   "Consent collection and withdrawal paths need work.",
        "sentinel":    "Downstream harm vectors warrant extra safeguards.",
        "sage":        "Considers broader consequences and wellbeing.",
        "philosopher": "Holds up across the major frameworks.",
        "guardian":    "Regulatory mapping shows alignment.",
    }
    score_by_id = {
        "steward": 76, "advocate": 82, "beacon": 45,
        "custodian": 50, "sentinel": 60, "sage": 70,
        "philosopher": 60, "guardian": 88,
    }
    deliberation_text = "".join(
        f'{aid}: {{"id": "{aid}", "score": {score_by_id[aid]}, "verdict": "pass", "flags": ["ok"], "reasoning": "{reasoning_by_id[aid]}"}}\n'
        for aid in AGENT_ORDER
    )
    follow_up_text = '{"id": "beacon", "score": 80, "verdict": "pass", "flags": ["ok"], "reasoning": "I weighed the disclosure gap..."}'

    client = MagicMock(spec=LLMClient)
    client.api_key = "sk-test"
    client.base_url = "https://example.com"
    client.model = "test-model"
    client.timeout = 30

    async def fake_stream(prompt, system=None):
        if "follow-up" in prompt.lower() or "follow up" in prompt.lower():
            # One char at a time
            for ch in follow_up_text:
                yield ch
        else:
            # One char at a time
            for ch in deliberation_text:
                yield ch
    client.evaluate_stream = fake_stream
    return client


@pytest.fixture
def client(fake_streaming_llm):
    """A TestClient with the LLM dependency overridden."""
    from ethics_canvas.api import get_llm
    app.dependency_overrides[get_llm] = lambda: fake_streaming_llm
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
