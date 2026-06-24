# Brief — Ethical Panel Agent Expansion

## Context

The Ethical Panel currently uses 6 AI agent personas to evaluate business decisions through distinct ethical lenses. After auditing coverage, two gaps were identified:

1. **Privacy & Consent** — Beacon (transparency/honesty) doesn't cover "should you be doing this at all?" only "are you being honest about it?"
2. **Harm / Non-maleficence** — No agent owns "does this decision cause suffering?" as a primary lens

This brief specifies the expanded agent roster and implementation scope.

## Decision

Expand to **7 agents**. Rationale:
- Harm is a primal ethical instinct — deserves its own voice, not a sub-lens
- Privacy/consent are distinct from transparency/honesty
- All 7 domains have clear boundaries with minimal overlap
- The product's value prop is "comprehensive ethical evaluation" — gaps undermine that

## Updated Agent Roster

All agents deliberate in parallel via SSE streaming. Each returns: reasoning text (streamed), a score (0–100), and contributes to the aggregate verdict (Pass / Caution / Flag).

### 1. 🌏 Steward — Environmental Impact
- Ecological footprint, resource consumption, waste
- Biodiversity, climate impact, pollution
- Long-term planetary health
- Catch: "Is this sustainable for the planet?"

### 2. 🤝 Advocate — Fairness & Equity
- Distributive justice, access, inclusion
- Marginalised groups, power dynamics
- Discrimination, bias, gatekeeping
- Catch: "Who does this leave out?"

### 3. 🔓 Beacon — Transparency, Honesty & Consent
- Full disclosure, truthfulness, deception check
- Informed consent, opt-in/opt-out
- Data rights, autonomy, bodily privacy
- Catch: "Are people being told the truth and given a choice?"

**Note:** Privacy/consent was added to Beacon's remit. This replaces the original narrower "Transparency & Honesty" brief.

### 4. 🛡️ Sentinel — Harm, Safety & Precaution — NEW
- Non-maleficence (do no harm)
- Physical, psychological, social, and financial harm
- Precautionary principle (when risks are uncertain, err on the side of safety)
- Safeguards, safety nets, downstream risk vectors
- Catch: "Could this hurt anyone — directly or downstream?"

**This is the new agent.** Adds ~$0.004 per 100 sessions to operating cost (DeepSeek Flash pricing).

### 5. 🧘 Sage — Conscious Leadership
- Integrity, character, long-term thinking
- Stakeholder trust, reputation, authenticity
- Moral courage to do the right thing even when costly
- Catch: "What would a wise leader do?"

### 6. ⚖️ Philosopher — Ethical Frameworks
- Deontology (duties, rules, universal principles)
- Utilitarianism (greatest good for greatest number)
- Virtue ethics (character, flourishing)
- Care ethics (relationships, interdependence, context)
- Catch: "What do the frameworks say?"

### 7. 📋 Guardian — Compliance & Legality
- Laws, regulations, industry standards
- Contracts, policies, fiduciary duty
- Jurisdictional considerations
- Catch: "Is this legal?"

## Implementation Notes

### Verdict Logic
Verdict remains Pass / Caution / Flag based on aggregate scoring across all 7 agents. Thresholds to be confirmed but suggested:
- All agents ≥ 70: Pass
- Any agent 40–69: Caution
- Any agent < 40: Flag

### UI considerations
- 7 agents requires a layout adjustment from the current 6. Options:
  - 2 rows: 4 + 3 layout
  - Single row of 7 (may need tighter cards)
  - Circular/council-ring layout with centred verdict
- The verdict strip at top remains unchanged
- @-mention follow-up chat works for all 7

### Agent system prompt structure
Each agent prompt should contain:
1. Role definition (one paragraph — who they are)
2. Specific lens instructions (what to evaluate)
3. Scoring guidance (how to map reasoning to 0–100)
4. A guardrail: "If this decision is outside your lens, say so and score 50 (neutral)"

### Existing tests
100-session load test exists at [current path]. After adding Sentinel, re-run load test to confirm:
- 98%+ deliberation success rate maintained
- ~8s deliberation time maintained
- Cost per 100 sessions stays under $0.04

## Files to touch

| File | Change |
|------|--------|
| `agents/` or equivalent config | Add Sentinel definition + system prompt |
| Main deliberation engine | Add 7th parallel SSE stream |
| Frontend verdict component | Update layout for 7 agents |
| Frontend streaming component | Add Sentinel card + icon |
| Verdict logic | Update aggregation to include 7th score |
| README | Update agent list, tagline (if needed) |
| Load test | Re-run and update benchmarks |
| `AGENTS.md` or similar | Update if exists |

## Open Questions

- Should Sentinel's icon be 🛡️ (shield) or something else? (⚔️ 🚨 ⚠️)
- Verdict thresholds — keep current or tune for 7?
- Does the tagline "Six ethical agents. One decision. Clear conscience." need updating?
  - If we commit to 7, yes. Options: "Seven ethical agents. One verdict. Clear conscience." or drop the number entirely.
- Name implications: if we rename the product, "Council of Six" and "SixVerdict" no longer fit with 7 agents. Names that don't encode a count (Verdict, EthicalPanel, The Council) are future-proof.

## Priority

1. Add Sentinel definition + system prompt (blocker)
2. Update deliberation engine to stream 7th agent (blocker)
3. Update UI for 7 columns/layout (depends on 1+2)
4. Re-run load test (after 1+2+3)
5. Update README/docs (can happen in parallel)
