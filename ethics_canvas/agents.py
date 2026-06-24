"""8 ethical agent personas.

Source of truth for the council. Keys are short ids that match the
design's contract (and the LLM prompt's expected output). Colors are
OKLch strings so the frontend can use them as CSS custom-property
values without conversion.
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class Agent:
    id: str
    name: str
    focus: str
    color: str
    prompt_suffix: str


AGENTS: dict[str, Agent] = {
    "steward": Agent(
        id="steward",
        name="Steward",
        focus="Environmental Impact",
        color="oklch(58% 0.14 165)",
        prompt_suffix=(
            "Evaluate this decision primarily through its impact on the natural "
            "environment — resources, emissions, waste, biodiversity, and "
            "long-term ecological health."
        ),
    ),
    "advocate": Agent(
        id="advocate",
        name="Advocate",
        focus="Fairness & Equity",
        color="oklch(58% 0.16 305)",
        prompt_suffix=(
            "Evaluate this decision primarily through who benefits, who bears "
            "the cost, and whether the distribution of outcomes is equitable "
            "across all stakeholders."
        ),
    ),
    "beacon": Agent(
        id="beacon",
        name="Beacon",
        focus="Transparency & Honesty",
        color="oklch(72% 0.14 80)",
        prompt_suffix=(
            "Evaluate this decision primarily through how visible, explainable, "
            "and honest it is — would you publish this decision in full?"
        ),
    ),
    "custodian": Agent(
        id="custodian",
        name="Custodian",
        focus="Privacy & Consent",
        color="oklch(60% 0.12 200)",
        prompt_suffix=(
            "Evaluate this decision primarily through privacy and consent — "
            "what information is collected about people, how consent is "
            "obtained and withdrawn, what rights people have to their data "
            "and bodily autonomy, and whether opt-in/opt-out is real or "
            "coerced."
        ),
    ),
    "sentinel": Agent(
        id="sentinel",
        name="Sentinel",
        focus="Harm & Safety",
        color="oklch(68% 0.16 50)",
        prompt_suffix=(
            "Evaluate this decision primarily through harm and safety — "
            "who could be hurt (physically, psychologically, socially, "
            "financially), what safeguards exist, and whether the "
            "precautionary principle applies when risks are uncertain or "
            "downstream."
        ),
    ),
    "sage": Agent(
        id="sage",
        name="Sage",
        focus="Wisdom",
        color="oklch(56% 0.14 250)",
        prompt_suffix=(
            "Evaluate this decision primarily through the lens of wisdom — "
            "long-term consequences, lessons from experience, integration of "
            "competing goods, and the difference between cleverness and "
            "right judgment."
        ),
    ),
    "philosopher": Agent(
        id="philosopher",
        name="Philosopher",
        focus="Ethical Frameworks",
        color="oklch(60% 0.16 350)",
        prompt_suffix=(
            "Evaluate this decision through multiple ethical frameworks — "
            "deontology (duty), utilitarianism (outcomes), virtue ethics "
            "(character), and care ethics (relationships)."
        ),
    ),
    "guardian": Agent(
        id="guardian",
        name="Guardian",
        focus="Compliance & Legality",
        color="oklch(50% 0.06 250)",
        prompt_suffix=(
            "Evaluate this decision primarily through its legal and regulatory "
            "compliance — does it meet obligations? Are there loopholes or "
            "grey areas?"
        ),
    ),
}


AGENT_ORDER: list[str] = [
    "steward",
    "advocate",
    "beacon",
    "custodian",
    "sentinel",
    "sage",
    "philosopher",
    "guardian",
]
