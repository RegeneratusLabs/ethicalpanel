"""Tests for the 8 ethical agent personas."""
from ethics_canvas.agents import AGENTS, AGENT_ORDER


EXPECTED_IDS = {
    "steward", "advocate", "beacon", "custodian",
    "sentinel", "sage", "philosopher", "guardian",
}
EXPECTED_ORDER = [
    "steward", "advocate", "beacon", "custodian",
    "sentinel", "sage", "philosopher", "guardian",
]


def test_eight_agents():
    assert len(AGENTS) == 8
    assert set(AGENTS.keys()) == EXPECTED_IDS


def test_agent_order_matches_design():
    assert AGENT_ORDER == EXPECTED_ORDER


def test_each_agent_has_required_fields():
    for agent_id, agent in AGENTS.items():
        assert agent.id == agent_id
        assert agent.name and isinstance(agent.name, str)
        assert agent.focus and isinstance(agent.focus, str)
        assert agent.color.startswith("oklch(") and agent.color.endswith(")")
        assert agent.prompt_suffix and isinstance(agent.prompt_suffix, str)
        assert not any(ord(c) > 0x2000 for c in agent.name), \
            f"{agent_id}.name contains emoji: {agent.name!r}"


def test_agent_colors_match_design():
    expected = {
        "steward":     "oklch(58% 0.14 165)",
        "advocate":    "oklch(58% 0.16 305)",
        "beacon":      "oklch(72% 0.14 80)",
        "custodian":   "oklch(60% 0.12 200)",
        "sentinel":    "oklch(68% 0.16 50)",
        "sage":        "oklch(56% 0.14 250)",
        "philosopher": "oklch(60% 0.16 350)",
        "guardian":    "oklch(50% 0.06 250)",
    }
    for agent_id, color in expected.items():
        assert AGENTS[agent_id].color == color, (
            f"{agent_id}: expected {color!r}, got {AGENTS[agent_id].color!r}"
        )
