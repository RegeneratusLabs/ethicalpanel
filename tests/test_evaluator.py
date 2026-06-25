"""Tests for the deliberation evaluator."""
import pytest

from ethics_canvas.agents import AGENT_ORDER
from ethics_canvas.evaluator import (
    Verdict,
    AgentResult,
    build_deliberation_prompt,
    build_summary_prompt,
    stream_deliberation,
    stream_summary,
    _parse_deliberation_stream,
    _find_balanced_json,
)


def _async_iter(items):
    async def gen():
        for item in items:
            yield item
    return gen()


def test_verdict_values():
    assert Verdict.pass_.value == "pass"
    assert Verdict.caution.value == "caution"
    assert Verdict.flag.value == "flag"


def test_agent_result_round_trip():
    r = AgentResult(
        id="steward",
        score=76,
        verdict=Verdict.caution,
        flags=["Energy concern"],
        reasoning="Meaningful footprint concerns.",
    )
    assert r.id == "steward"
    assert r.score == 76
    assert r.verdict is Verdict.caution
    assert r.flags == ["Energy concern"]


def test_build_deliberation_prompt_includes_situation():
    prompt = build_deliberation_prompt("Sell anonymized usage data?")
    assert "Sell anonymized usage data?" in prompt


def test_build_deliberation_prompt_includes_all_agents():
    prompt = build_deliberation_prompt("test")
    for agent_id in AGENT_ORDER:
        assert agent_id in prompt, f"prompt missing {agent_id}"


def test_build_deliberation_prompt_states_strict_format():
    prompt = build_deliberation_prompt("test")
    # The LLM must output one agent per line
    assert "one agent" in prompt.lower() or "per line" in prompt.lower()
    # And the JSON shape must be specified
    assert "score" in prompt
    assert "verdict" in prompt
    assert "flags" in prompt
    assert "reasoning" in prompt


def test_build_deliberation_prompt_includes_verdict_thresholds():
    prompt = build_deliberation_prompt("test")
    # The LLM needs to know what scores map to which verdicts
    assert "pass" in prompt
    assert "caution" in prompt
    assert "flag" in prompt


def test_build_deliberation_prompt_includes_id_in_example_output():
    """The example JSON in the prompt includes the 'id' field (matches the spec)."""
    prompt = build_deliberation_prompt("test")
    assert '"id"' in prompt
    # And each agent id should appear both as a prefix and as the 'id' value
    for aid in AGENT_ORDER:
        assert f'"id": "{aid}"' in prompt, f"prompt missing 'id' for {aid}"


@pytest.mark.asyncio
async def test_find_balanced_json_simple():
    """Balanced-bracket scanner finds a simple JSON object."""
    text = 'preamble {"a": 1, "b": [2, 3]} tail'
    start, end = _find_balanced_json(text, open_pos=text.index("{"))
    assert text[start:end + 1] == '{"a": 1, "b": [2, 3]}'


@pytest.mark.asyncio
async def test_find_balanced_json_with_strings():
    """Strings containing braces don't break the scanner."""
    text = 'x {"a": "with } in it", "b": 2} y'
    start, end = _find_balanced_json(text, open_pos=text.index("{"))
    assert text[start:end + 1] == '{"a": "with } in it", "b": 2}'


@pytest.mark.asyncio
async def test_find_balanced_json_incomplete():
    """Incomplete JSON returns None (waits for more data)."""
    text = 'x {"a": 1, "b": [2,'
    start, end = _find_balanced_json(text, open_pos=text.index("{"))
    assert (start, end) == (text.index("{"), None) or end is None


@pytest.mark.asyncio
async def test_parse_stream_yields_all_results_in_order():
    """A complete LLM response yields 8 AgentResults in agent order."""
    _SCORES = {
        "steward": (76, "caution"), "advocate": (82, "pass"), "beacon": (45, "caution"),
        "custodian": (50, "caution"), "sentinel": (60, "pass"), "sage": (70, "pass"),
        "philosopher": (60, "pass"), "guardian": (88, "pass"),
    }
    _REASONING = {
        "steward": "Footprint concerns.", "advocate": "Fair.",
        "beacon": "Disclosure gap.", "custodian": "Consent path unclear.",
        "sentinel": "Safeguards present.", "sage": "Forward-looking.",
        "philosopher": "Holds up.", "guardian": "Regs met.",
    }
    chunks = [
        f'{aid}: {{"id": "{aid}", "score": {_SCORES[aid][0]}, "verdict": "{_SCORES[aid][1]}", "flags": ["x"], "reasoning": "{_REASONING[aid]}"}}\n'
        for aid in AGENT_ORDER
    ]
    events = []
    async for e in _parse_deliberation_stream(_async_iter(chunks)):
        events.append(e)
    results = [e["result"] for e in events if e["type"] == "agent_result"]
    assert len(results) == len(AGENT_ORDER)
    assert [r.id for r in results] == AGENT_ORDER
    assert results[0].score == 76
    assert results[0].verdict is Verdict.caution
    assert results[1].verdict is Verdict.pass_
    assert results[-1].id == "guardian"


@pytest.mark.asyncio
async def test_parse_stream_handles_incremental_chunks():
    """The parser yields results as soon as enough data is available,
    not waiting for the full stream to end."""
    chunks = [
        'steward: {"id": "steward", "sco',
        're": 76, "verdict": "caution"',
        ', "flags": [], "reasoning": "x"}\n',
        'advocate: {"id": "advocate", "score": 80, "verdict": "pass", "flags": [], "reasoning": "y"}\n',
        'beacon: {"id": "beacon", "score": 50, "verdict": "caution", "flags": [], "reasoning": "z"}\n',
        'custodian: {"id": "custodian", "score": 50, "verdict": "caution", "flags": [], "reasoning": "ca"}\n',
        'sentinel: {"id": "sentinel", "score": 60, "verdict": "pass", "flags": [], "reasoning": "sa"}\n',
        'sage: {"id": "sage", "score": 60, "verdict": "pass", "flags": [], "reasoning": "a"}\n',
        'philosopher: {"id": "philosopher", "score": 55, "verdict": "caution", "flags": [], "reasoning": "b"}\n',
        'guardian: {"id": "guardian", "score": 70, "verdict": "pass", "flags": [], "reasoning": "c"}\n',
    ]
    events = []
    async for e in _parse_deliberation_stream(_async_iter(chunks)):
        events.append(e)
    results = [e["result"] for e in events if e["type"] == "agent_result"]
    assert len(results) == 8
    assert results[0].id == "steward"
    assert results[0].score == 76
    # The parser yielded results incrementally, not at end-of-stream
    # (we can't directly assert this from the result list, but the
    # 8 successful results prove the chunks were reassembled correctly)


@pytest.mark.asyncio
async def test_parse_stream_handles_prose_before_first_agent():
    """The parser ignores any prose that appears before the first agent id."""
    chunks = [
        'Sure, here is the evaluation:\n\n',
        'steward: {"id": "steward", "score": 50, "verdict": "caution", "flags": [], "reasoning": "ok"}\n',
        'advocate: {"id": "advocate", "score": 80, "verdict": "pass", "flags": [], "reasoning": "a"}\n',
        'beacon: {"id": "beacon", "score": 60, "verdict": "pass", "flags": [], "reasoning": "b"}\n',
        'custodian: {"id": "custodian", "score": 60, "verdict": "pass", "flags": [], "reasoning": "cu"}\n',
        'sentinel: {"id": "sentinel", "score": 65, "verdict": "pass", "flags": [], "reasoning": "se"}\n',
        'sage: {"id": "sage", "score": 70, "verdict": "pass", "flags": [], "reasoning": "c"}\n',
        'philosopher: {"id": "philosopher", "score": 65, "verdict": "pass", "flags": [], "reasoning": "d"}\n',
        'guardian: {"id": "guardian", "score": 75, "verdict": "pass", "flags": [], "reasoning": "e"}\n',
    ]
    events = []
    async for e in _parse_deliberation_stream(_async_iter(chunks)):
        events.append(e)
    results = [e["result"] for e in events if e["type"] == "agent_result"]
    assert len(results) == 8
    assert results[0].id == "steward"


@pytest.mark.asyncio
async def test_parse_stream_raises_on_missing_agent():
    """If the stream ends without all 6 agents, raise LLMError."""
    from ethics_canvas.llm import LLMError
    chunks = [
        'steward: {"id": "steward", "score": 50, "verdict": "caution", "flags": [], "reasoning": "x"}\n',
    ]
    with pytest.raises(LLMError, match="missing"):
        async for r in _parse_deliberation_stream(_async_iter(chunks)):
            pass


@pytest.mark.asyncio
async def test_parse_stream_raises_on_malformed_json():
    """A line that doesn't parse as JSON raises LLMError."""
    from ethics_canvas.llm import LLMError
    chunks = [
        'steward: not valid json\n',
    ]
    with pytest.raises(LLMError, match="malformed|json|shape|missing"):
        async for r in _parse_deliberation_stream(_async_iter(chunks)):
            pass


@pytest.mark.asyncio
async def test_parse_stream_raises_on_bad_verdict():
    """An unknown verdict value raises LLMError."""
    from ethics_canvas.llm import LLMError
    chunks = [
        'steward: {"score": 50, "verdict": "yellow", "flags": [], "reasoning": "x"}\n',
    ]
    with pytest.raises(LLMError):
        async for r in _parse_deliberation_stream(_async_iter(chunks)):
            pass


@pytest.mark.asyncio
async def test_parse_stream_raises_on_id_mismatch():
    """If the JSON's id field doesn't match the expected agent id, raise LLMError."""
    from ethics_canvas.llm import LLMError
    # 8 agents but steward claims to be advocate in its JSON
    chunks = [
        'steward: {"id": "advocate", "score": 50, "verdict": "caution", "flags": [], "reasoning": "x"}\n',
        'advocate: {"score": 80, "verdict": "pass", "flags": [], "reasoning": "a"}\n',
        'beacon: {"score": 60, "verdict": "pass", "flags": [], "reasoning": "b"}\n',
        'custodian: {"score": 50, "verdict": "caution", "flags": [], "reasoning": "c"}\n',
        'sentinel: {"score": 65, "verdict": "pass", "flags": [], "reasoning": "d"}\n',
        'sage: {"score": 70, "verdict": "pass", "flags": [], "reasoning": "e"}\n',
        'philosopher: {"score": 65, "verdict": "pass", "flags": [], "reasoning": "f"}\n',
        'guardian: {"score": 75, "verdict": "pass", "flags": [], "reasoning": "g"}\n',
    ]
    with pytest.raises(LLMError, match="id mismatch"):
        async for r in _parse_deliberation_stream(_async_iter(chunks)):
            pass


def _fake_streaming_llm(chunks_per_call):
    """Build a fake LLMClient that yields pre-canned chunks for evaluate_stream."""
    from ethics_canvas.llm import LLMClient
    chunks = chunks_per_call.pop(0)

    class FakeClient(LLMClient):
        def __init__(self):
            pass  # skip parent init

        async def evaluate_stream(self, prompt, system=None):
            for chunk in chunks:
                yield chunk
    return FakeClient()


@pytest.mark.asyncio
async def test_stream_deliberation_yields_all_results_in_order():
    """End-to-end: a fake streaming LLM returns 8 valid agent lines."""
    _SCORES = {
        "steward": (76, "caution"), "advocate": (82, "pass"), "beacon": (45, "caution"),
        "custodian": (50, "caution"), "sentinel": (60, "pass"), "sage": (70, "pass"),
        "philosopher": (60, "pass"), "guardian": (88, "pass"),
    }
    full_response = "".join(
        f'{aid}: {{"id": "{aid}", "score": {_SCORES[aid][0]}, "verdict": "{_SCORES[aid][1]}", "flags": ["x"], "reasoning": "r{i}"}}\n'
        for i, aid in enumerate(AGENT_ORDER)
    )
    llm = _fake_streaming_llm([[full_response]])

    events = []
    async for e in stream_deliberation("test prompt", llm=llm):
        events.append(e)
    results = [e["result"] for e in events if e["type"] == "agent_result"]

    assert [r.id for r in results] == AGENT_ORDER
    assert all(isinstance(r.verdict, Verdict) for r in results)


@pytest.mark.asyncio
async def test_stream_deliberation_passes_prompt_to_llm():
    """The user's prompt is included in the LLM call."""
    from unittest.mock import AsyncMock

    class MockClient:
        def __init__(self):
            self.received_prompt = None
        async def evaluate_stream(self, prompt, system=None):
            self.received_prompt = prompt
            yield (
                'steward: {"id": "steward", "score": 50, "verdict": "caution", "flags": [], "reasoning": "x"}\n'
                'advocate: {"id": "advocate", "score": 50, "verdict": "caution", "flags": [], "reasoning": "x"}\n'
                'beacon: {"id": "beacon", "score": 50, "verdict": "caution", "flags": [], "reasoning": "x"}\n'
                'custodian: {"id": "custodian", "score": 50, "verdict": "caution", "flags": [], "reasoning": "x"}\n'
                'sentinel: {"id": "sentinel", "score": 50, "verdict": "caution", "flags": [], "reasoning": "x"}\n'
                'sage: {"id": "sage", "score": 50, "verdict": "caution", "flags": [], "reasoning": "x"}\n'
                'philosopher: {"id": "philosopher", "score": 50, "verdict": "caution", "flags": [], "reasoning": "x"}\n'
                'guardian: {"id": "guardian", "score": 50, "verdict": "caution", "flags": [], "reasoning": "x"}\n'
            )
    client = MockClient()
    async for _ in stream_deliberation("My situation: should I do X?", llm=client):
        pass
    assert "My situation: should I do X?" in client.received_prompt


@pytest.mark.asyncio
async def test_stream_deliberation_propagates_llm_error():
    """A malformed stream raises LLMError."""
    from ethics_canvas.llm import LLMError
    llm = _fake_streaming_llm([['steward: bad json\n']])
    with pytest.raises(LLMError):
        async for _ in stream_deliberation("test", llm=llm):
            pass


from ethics_canvas.evaluator import build_follow_up_prompt, stream_follow_up


def test_build_follow_up_prompt_includes_agent_focus():
    """The follow-up prompt primes the agent with its focus."""
    prompt = build_follow_up_prompt(
        follow_up_text="@Beacon why that score?",
        agent_id="beacon",
        context=[
            {"role": "user", "content": "Sell anonymized usage data?"},
            {"role": "assistant", "agent_id": "beacon",
             "content": "Disclosure gap is the concern."},
        ],
    )
    assert "beacon" in prompt.lower() or "Beacon" in prompt
    assert "Transparency" in prompt or "transparency" in prompt


def test_build_follow_up_prompt_includes_context():
    """The follow-up prompt includes the prior conversation."""
    prompt = build_follow_up_prompt(
        follow_up_text="why?",
        agent_id="beacon",
        context=[
            {"role": "user", "content": "Sell anonymized usage data?"},
            {"role": "assistant", "agent_id": "beacon",
             "content": "Disclosure gap."},
        ],
    )
    assert "Sell anonymized usage data?" in prompt
    assert "Disclosure gap." in prompt
    assert "why?" in prompt


def test_build_follow_up_prompt_specifies_output_format():
    """The follow-up prompt tells the LLM the expected JSON shape (single line)."""
    prompt = build_follow_up_prompt(
        follow_up_text="why?",
        agent_id="beacon",
        context=[],
    )
    assert "score" in prompt
    assert "verdict" in prompt
    assert "flags" in prompt
    assert "reasoning" in prompt


def test_build_follow_up_prompt_rejects_unknown_agent():
    """An unknown agent_id raises LLMError."""
    from ethics_canvas.llm import LLMError
    with pytest.raises(LLMError, match="unknown agent"):
        build_follow_up_prompt("why?", agent_id="nonexistent", context=[])


@pytest.mark.asyncio
async def test_stream_follow_up_yields_single_result():
    """The follow-up yields exactly one AgentResult for the @-mentioned agent."""
    full_response = (
        '{"id": "beacon", "score": 80, "verdict": "pass", "flags": ["Auditable"], "reasoning": "I weighed..."}'
    )
    llm = _fake_streaming_llm([[full_response]])

    events = []
    async for e in stream_follow_up(
        follow_up_text="why that score?",
        agent_id="beacon",
        context=[],
        llm=llm,
    ):
        events.append(e)
    results = [e["result"] for e in events if e["type"] == "agent_result"]
    assert len(results) == 1
    assert results[0].id == "beacon"


@pytest.mark.asyncio
async def test_stream_follow_up_includes_context_in_prompt():
    """The user's prior conversation is part of the LLM call."""
    class MockClient:
        def __init__(self):
            self.received_prompt = None
        async def evaluate_stream(self, prompt, system=None):
            self.received_prompt = prompt
            yield (
                '{"id": "beacon", "score": 80, "verdict": "pass", "flags": [], "reasoning": "x"}'
            )
    client = MockClient()
    async for _ in stream_follow_up(
        follow_up_text="why?",
        agent_id="beacon",
        context=[
            {"role": "user", "content": "Sell data?"},
            {"role": "assistant", "agent_id": "beacon", "content": "Disclosure gap."},
        ],
        llm=client,
    ):
        pass
    assert "Sell data?" in client.received_prompt
    assert "Disclosure gap." in client.received_prompt


@pytest.mark.asyncio
async def test_parse_stream_yields_agent_start():
    """A complete LLM response yields agent_start events for each agent."""
    chunks = [
        'steward: {"id": "steward", "score": 76, "verdict": "caution", "flags": ["Energy"], "reasoning": "Footprint concerns."}\n',
        'advocate: {"id": "advocate", "score": 82, "verdict": "pass", "flags": ["Equitable"], "reasoning": "Fair."}\n',
        'beacon: {"id": "beacon", "score": 45, "verdict": "caution", "flags": ["Opacity"], "reasoning": "Disclosure gap."}\n',
        'custodian: {"id": "custodian", "score": 50, "verdict": "caution", "flags": ["Consent"], "reasoning": "Consent path."}\n',
        'sentinel: {"id": "sentinel", "score": 60, "verdict": "pass", "flags": ["Safe"], "reasoning": "Safeguards ok."}\n',
        'sage: {"id": "sage", "score": 70, "verdict": "pass", "flags": ["Aligned"], "reasoning": "Forward-looking."}\n',
        'philosopher: {"id": "philosopher", "score": 60, "verdict": "pass", "flags": ["Sound"], "reasoning": "Holds up."}\n',
        'guardian: {"id": "guardian", "score": 88, "verdict": "pass", "flags": ["Compliant"], "reasoning": "Regs met."}\n',
    ]
    events = []
    async for e in _parse_deliberation_stream(_async_iter(chunks)):
        events.append(e)
    starts = [e for e in events if e["type"] == "agent_start"]
    assert len(starts) == 8
    assert [s["id"] for s in starts] == AGENT_ORDER


@pytest.mark.asyncio
async def test_parse_stream_yields_reasoning_deltas():
    """Each agent's reasoning text is emitted as one or more deltas."""
    chunks = [
        'steward: {"id": "steward", "score": 76, "verdict": "caution", "flags": ["Energy"], "reasoning": "Hello world',
        ' extra text"}\n',
        'advocate: {"id": "advocate", "score": 82, "verdict": "pass", "flags": ["Equitable"], "reasoning": "Fair."}\n',
        'beacon: {"id": "beacon", "score": 45, "verdict": "caution", "flags": ["Opacity"], "reasoning": "Disclosure gap."}\n',
        'custodian: {"id": "custodian", "score": 50, "verdict": "caution", "flags": ["Consent"], "reasoning": "Consent path."}\n',
        'sentinel: {"id": "sentinel", "score": 60, "verdict": "pass", "flags": ["Safe"], "reasoning": "Safeguards ok."}\n',
        'sage: {"id": "sage", "score": 70, "verdict": "pass", "flags": ["Aligned"], "reasoning": "Forward-looking."}\n',
        'philosopher: {"id": "philosopher", "score": 60, "verdict": "pass", "flags": ["Sound"], "reasoning": "Holds up."}\n',
        'guardian: {"id": "guardian", "score": 88, "verdict": "pass", "flags": ["Compliant"], "reasoning": "Regs met."}\n',
    ]
    events = []
    async for e in _parse_deliberation_stream(_async_iter(chunks)):
        events.append(e)
    deltas = [e for e in events if e["type"] == "reasoning_delta"]
    # The steward reasoning is "Hello world extra text" — should yield at least one delta
    steward_deltas = [d for d in deltas if d["id"] == "steward"]
    assert len(steward_deltas) >= 1
    full_steward = "".join(d["text"] for d in steward_deltas)
    assert full_steward == "Hello world extra text"


@pytest.mark.asyncio
async def test_parse_stream_handles_per_character_chunks():
    """The parser handles one-character chunks (real LLM behavior)."""
    full = (
        'steward: {"id": "steward", "score": 76, "verdict": "caution", "flags": ["E"], "reasoning": "Footprint."}\n'
        'advocate: {"id": "advocate", "score": 82, "verdict": "pass", "flags": ["E"], "reasoning": "Fair."}\n'
        'beacon: {"id": "beacon", "score": 45, "verdict": "caution", "flags": ["O"], "reasoning": "Gap."}\n'
        'custodian: {"id": "custodian", "score": 50, "verdict": "caution", "flags": ["C"], "reasoning": "Path."}\n'
        'sentinel: {"id": "sentinel", "score": 60, "verdict": "pass", "flags": ["S"], "reasoning": "Safe."}\n'
        'sage: {"id": "sage", "score": 70, "verdict": "pass", "flags": ["A"], "reasoning": "Forward."}\n'
        'philosopher: {"id": "philosopher", "score": 60, "verdict": "pass", "flags": ["S"], "reasoning": "Holds."}\n'
        'guardian: {"id": "guardian", "score": 88, "verdict": "pass", "flags": ["C"], "reasoning": "Regs."}\n'
    )
    chunks = [c for c in full]  # one char per chunk
    events = []
    async for e in _parse_deliberation_stream(_async_iter(chunks)):
        events.append(e)
    types_count = {}
    for e in events:
        types_count[e["type"]] = types_count.get(e["type"], 0) + 1
    assert types_count.get("agent_start", 0) == 8
    assert types_count.get("agent_result", 0) == 8
    assert types_count.get("reasoning_delta", 0) >= 8  # at least one per agent


@pytest.mark.asyncio
async def test_parse_stream_handles_escaped_quotes_in_reasoning():
    """Reasoning text with escaped quotes is parsed correctly when split
    across chunks (so the parser must stream the reasoning)."""
    chunks = [
        'steward: {"id": "steward", "score": 50, "verdict": "caution", "flags": [], "reasoning": "He said \\"hel',
        'lo\\" today"}\n',
        'advocate: {"id": "advocate", "score": 50, "verdict": "caution", "flags": [], "reasoning": "a"}\n',
        'beacon: {"id": "beacon", "score": 50, "verdict": "caution", "flags": [], "reasoning": "b"}\n',
        'custodian: {"id": "custodian", "score": 50, "verdict": "caution", "flags": [], "reasoning": "c"}\n',
        'sentinel: {"id": "sentinel", "score": 50, "verdict": "caution", "flags": [], "reasoning": "d"}\n',
        'sage: {"id": "sage", "score": 50, "verdict": "caution", "flags": [], "reasoning": "e"}\n',
        'philosopher: {"id": "philosopher", "score": 50, "verdict": "caution", "flags": [], "reasoning": "f"}\n',
        'guardian: {"id": "guardian", "score": 50, "verdict": "caution", "flags": [], "reasoning": "g"}\n',
    ]
    events = []
    async for e in _parse_deliberation_stream(_async_iter(chunks)):
        events.append(e)
    steward_deltas = [d for d in events if d.get("type") == "reasoning_delta" and d.get("id") == "steward"]
    full_steward = "".join(d["text"] for d in steward_deltas)
    assert full_steward == 'He said "hello" today'


# --- build_summary_prompt ---

def _dummy_results():
    return [
        AgentResult(id="steward",    score=95, verdict=Verdict.pass_,    flags=[],            reasoning="Minimal footprint."),
        AgentResult(id="advocate",   score=10, verdict=Verdict.flag,     flags=["unfair"],    reasoning="Exploits power imbalance."),
        AgentResult(id="beacon",     score=5,  verdict=Verdict.flag,     flags=["opaque"],    reasoning="Hidden monetization."),
        AgentResult(id="custodian",  score=5,  verdict=Verdict.flag,     flags=["no_consent"], reasoning="No consent mechanism."),
        AgentResult(id="sentinel",   score=10, verdict=Verdict.flag,     flags=["risk"],      reasoning="Data breach potential."),
        AgentResult(id="sage",       score=20, verdict=Verdict.flag,     flags=["short_term"], reasoning="Short-term thinking."),
        AgentResult(id="philosopher", score=5, verdict=Verdict.flag,     flags=["autonomy"],  reasoning="Treats users as means."),
        AgentResult(id="guardian",   score=10, verdict=Verdict.flag,     flags=["gdpr"],      reasoning="GDPR violation risk."),
    ]


def test_build_summary_prompt_structure():
    results = _dummy_results()
    situation = "Should I sell user data?"
    system, user = build_summary_prompt(situation, results)
    assert "neutral synthesizer" in system
    assert "single paragraph" in system
    assert "prose" in system
    assert situation in user
    for r in results:
        assert r.id in user
        assert r.reasoning in user


def test_build_summary_prompt_includes_flags():
    results = _dummy_results()
    system, user = build_summary_prompt("x", results)
    # Flags are included when non-empty
    assert "unfair" in user
    assert "gdpr" in user
    # Verdict + score are formatted
    assert "95/100" in user
    assert "verdict=pass" in user


# --- stream_summary ---

class _StubLLM:
    def __init__(self, chunks):
        self._chunks = chunks
    async def evaluate_stream(self, prompt, system=None):
        for c in self._chunks:
            yield c


@pytest.mark.asyncio
async def test_stream_summary_event_order():
    llm = _StubLLM(["The ", "council ", "flagged ", "this."])
    events = []
    async for e in stream_summary("test situation", _dummy_results(), llm=llm):
        events.append(e)
    types = [e["type"] for e in events]
    assert types[0] == "summary_start"
    assert types[-1] == "summary_result"
    deltas = [e for e in events if e["type"] == "summary_delta"]
    assert len(deltas) == 4
    assert "".join(d["text"] for d in deltas) == "The council flagged this."
    assert events[-1]["text"] == "The council flagged this."


@pytest.mark.asyncio
async def test_stream_summary_handles_empty_chunks():
    llm = _StubLLM(["hello", "", " ", "world"])
    events = []
    async for e in stream_summary("x", _dummy_results(), llm=llm):
        events.append(e)
    # Empty string chunks should be filtered, not emitted as deltas
    deltas = [e for e in events if e["type"] == "summary_delta"]
    assert [d["text"] for d in deltas] == ["hello", " ", "world"]
    assert events[-1]["text"] == "hello world"


@pytest.mark.asyncio
async def test_stream_summary_empty_chunks_yields_only_start_and_result():
    """Even if the LLM yields nothing, we still emit start + result (empty)."""
    llm = _StubLLM([])
    events = []
    async for e in stream_summary("x", _dummy_results(), llm=llm):
        events.append(e)
    assert [e["type"] for e in events] == ["summary_start", "summary_result"]
    assert events[-1]["text"] == ""


@pytest.mark.asyncio
async def test_stream_summary_re_raises_llm_error():
    from ethics_canvas.llm import LLMError
    class _ErrLLM:
        async def evaluate_stream(self, prompt, system=None):
            raise LLMError(500, "boom")
            if False:
                yield  # makes this an async generator
    llm = _ErrLLM()
    with pytest.raises(LLMError):
        async for _ in stream_summary("x", _dummy_results(), llm=llm):
            pass
