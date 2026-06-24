"""Real-LLM smoke test.

Skipped unless `EFC_RUN_SMOKE=1` and `DEEPSEEK_API_KEY` are set in
the environment. This test hits the network and depends on the real
DeepSeek service. Run it manually after unit tests pass.

It calls the new SSE endpoints via a synchronous wrapper and asserts
the response shape matches the design's contract.
"""
import json
import os

import pytest
from fastapi.testclient import TestClient

from ethics_canvas.api import app


pytestmark = pytest.mark.skipif(
    not (os.getenv("EFC_RUN_SMOKE") and os.getenv("DEEPSEEK_API_KEY")),
    reason="real LLM smoke test skipped (set EFC_RUN_SMOKE=1 and DEEPSEEK_API_KEY)",
)


def test_deliberate_smoke():
    client = TestClient(app)
    r = client.post("/api/deliberate", json={
        "prompt": "Should my SaaS company sell anonymized usage data to fund free tiers?",
    })
    assert r.status_code == 200
    body = r.text
    # 6 agent_result events
    assert body.count("event: agent_result") == 6
    # Final complete event
    assert "event: complete" in body
    # Parse all data lines and verify the shape
    for line in body.split("\n"):
        if not line.startswith("data: "):
            continue
        data = json.loads(line[len("data: "):])
        if "results" in data:
            # complete event
            for r in data["results"]:
                assert r["id"] in {
                    "steward", "advocate", "beacon",
                    "sage", "philosopher", "guardian",
                }
                assert isinstance(r["score"], int) and 0 <= r["score"] <= 100
                assert r["verdict"] in {"pass", "caution", "flag"}
                assert isinstance(r["flags"], list)
                assert isinstance(r["reasoning"], str)
        else:
            # agent_result event
            assert data["id"] in {
                "steward", "advocate", "beacon",
                "sage", "philosopher", "guardian",
            }
            assert isinstance(data["score"], int) and 0 <= data["score"] <= 100
            assert data["verdict"] in {"pass", "caution", "flag"}
