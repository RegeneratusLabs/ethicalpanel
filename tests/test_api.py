"""Tests for the FastAPI app."""
import json
import pytest

from ethics_canvas.llm import LLMError


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_list_agents_returns_array_of_eight(client):
    r = client.get("/api/agents")
    assert r.status_code == 200
    agents = r.json()
    assert isinstance(agents, list)
    assert len(agents) == 8
    assert [a["id"] for a in agents] == [
        "steward", "advocate", "beacon", "custodian",
        "sentinel", "sage", "philosopher", "guardian",
    ]
    for a in agents:
        assert a["name"]
        assert a["focus"]
        assert a["color"].startswith("oklch(")


def test_root_serves_ethics_council(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Ethical Panel" in r.text


def test_deliberate_happy_path_sse_stream(client, fake_streaming_llm):
    r = client.post("/api/deliberate", json={"prompt": "test situation"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    body = r.text
    # Per agent: 1 agent_start + N reasoning_delta + 1 agent_result = 8+ events
    assert body.count("event: agent_start") == 8
    assert body.count("event: agent_result") == 8
    assert body.count("event: reasoning_delta") >= 8  # at least 1 per agent
    assert "event: complete" in body
    # Every event has a data line with valid JSON
    for line in body.split("\n"):
        if line.startswith("data: "):
            json.loads(line[len("data: "):])


def test_deliberate_empty_prompt_422(client):
    r = client.post("/api/deliberate", json={"prompt": "   "})
    assert r.status_code == 422


def test_deliberate_missing_prompt_422(client):
    r = client.post("/api/deliberate", json={})
    assert r.status_code == 422


def test_deliberate_oversized_prompt_422(client, fake_settings):
    big = "x" * (fake_settings.idea_max_length + 1)
    r = client.post("/api/deliberate", json={"prompt": big})
    assert r.status_code == 422


def test_deliberate_llm_error_emits_error_event(client, fake_streaming_llm):
    async def failing_stream(prompt, system=None):
        raise LLMError(401, "bad key")
        yield ""  # unreachable; makes this a generator function
    fake_streaming_llm.evaluate_stream = failing_stream

    r = client.post("/api/deliberate", json={"prompt": "test"})
    assert r.status_code == 200
    assert "event: error" in r.text
    assert "bad key" in r.text


def test_follow_up_happy_path_sse_stream(client, fake_streaming_llm):
    r = client.post("/api/follow-up", json={
        "prompt": "@Beacon why that score?",
        "agent_id": "beacon",
        "context": [
            {"role": "user", "content": "Sell data?"},
            {"role": "assistant", "agent_id": "beacon", "content": "Disclosure gap."},
        ],
    })
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    body = r.text
    assert body.count("event: agent_start") == 1
    assert body.count("event: agent_result") == 1
    assert body.count("event: reasoning_delta") >= 1
    assert "event: complete" in body
    assert '"beacon"' in body


def test_follow_up_missing_agent_id_422(client):
    r = client.post("/api/follow-up", json={"prompt": "why?", "context": []})
    assert r.status_code == 422


def test_follow_up_unknown_agent_id_422(client):
    r = client.post("/api/follow-up", json={
        "prompt": "why?",
        "agent_id": "nonexistent",
        "context": [],
    })
    assert r.status_code == 422
