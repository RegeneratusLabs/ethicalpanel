# Ethical Panel

**Eight ethical agents. One decision. Clear conscience.**

[![Live](https://img.shields.io/badge/Live-ethicalpanel.com-2ea44f?style=for-the-badge)](https://ethicalpanel.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?style=for-the-badge)](LICENSE)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg?style=for-the-badge)](pyproject.toml)

A chat-based web app where 8 specialized AI agent personas deliberate on an ethical question together, streaming their reasoning in real time. Try it at **[ethicalpanel.com](https://ethicalpanel.com)**.

![Screenshot](static/screenshot.png)

## What it does

Describe a decision you're weighing — "Should I sell user data?" "Can I use this image?" "Is it OK to deploy on a Friday?" — and 8 agents deliberate in parallel, each through a distinct ethical lens. They stream their reasoning token-by-token. You can `@mention` any agent for a follow-up. The council reaches a verdict (pass / caution / flag) at the end.

## The agents

| Agent | Focus |
|---|---|
| 🌏 **Steward** | Environmental impact |
| 🤝 **Advocate** | Fairness & equity |
| 🔓 **Beacon** | Transparency & honesty |
| 🔐 **Custodian** | Privacy & consent |
| 🛡 **Sentinel** | Harm & safety |
| 🧘 **Sage** | Wisdom |
| ⚖ **Philosopher** | Ethical frameworks |
| 📋 **Guardian** | Compliance & legality |

## Tech stack

- **Backend**: Python 3.13, FastAPI, SSE streaming
- **Frontend**: Vanilla JS, no framework
- **LLM**: [DeepSeek](https://deepseek.com) via Anthropic-compatible API (the only external dep at runtime)
- **Fonts**: Self-hosted Inter + JetBrains Mono (no Google Fonts CDN)
- **Hosting**: Single VPS behind a [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/) (origin IP not exposed)

## Quick start (local)

```bash
# 1. Install uv (Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Clone and set up
git clone https://github.com/RegeneratusLabs/ethicalpanel.git
cd ethicalpanel

# 3. Configure
cp .env.example .env
# Edit .env and add your DEEPSEEK_API_KEY
chmod 600 .env

# 4. Run
uv sync
bash start.sh
```

Open <http://localhost:8001> in a browser.

The real-LLM smoke test (`tests/test_llm_smoke.py`) is auto-skipped unless `DEEPSEEK_API_KEY` is set.

## Self-hosting

The `deploy/` directory contains everything needed to run this on a fresh Ubuntu 24.04 VPS:

- `Caddyfile` — reverse proxy with strict security headers
- `ethical-panel.service` — hardened systemd unit
- `cloudflared-config.yml` — Cloudflare tunnel config template
- `bootstrap.sh` — one-shot provisioning script
- `README.md` — full deploy guide

See **[deploy/README.md](deploy/README.md)** for step-by-step.

## Configuration

| Env var | Required | Default | Notes |
|---|---|---|---|
| `DEEPSEEK_API_KEY` | yes | — | App refuses to start without it |
| `DEEPSEEK_BASE_URL` | no | `https://api.deepseek.com/anthropic` | Swap in any Anthropic-compatible endpoint |
| `DEEPSEEK_MODEL` | no | `deepseek-v4-flash` | |
| `IDEA_MAX_LENGTH` | no | `5000` | chars; longer ideas return 422 |
| `LOG_LEVEL` | no | `INFO` | |
| `REQUEST_TIMEOUT_S` | no | `60` | LLM HTTP timeout |

## API

| Route | Method | Body | Returns |
|---|---|---|---|
| `/api/health` | GET | — | `{status: "ok"}` |
| `/api/agents` | GET | — | 8 agent descriptors |
| `/api/deliberate` | POST | `{prompt: str}` | SSE: `agent_start`, `reasoning_delta`, `agent_result` × 8, `complete` |
| `/api/follow-up` | POST | `{prompt, agent_id, context}` | SSE: same shape, single agent |
| `/` | GET | — | `static/index.html` |
| `/static/*` | GET | — | static assets |

## Project structure

```
ethical-panel/
├── main.py                  # uvicorn entrypoint
├── start.sh                 # launcher
├── pyproject.toml
├── uv.lock
├── ethics_canvas/           # app code
│   ├── api.py               # FastAPI routes
│   ├── evaluator.py         # SSE parser, prompt builder
│   ├── agents.py            # 8 agent definitions
│   ├── llm.py               # LLM client
│   ├── config.py
│   └── logging.py
├── static/                  # SPA + fonts
│   ├── index.html
│   └── fonts/
├── tests/                   # 8 test files, ~80 tests
└── deploy/                  # VPS deploy artifacts (Caddyfile, systemd, CF tunnel, bootstrap)
```

## Development

```bash
uv sync --extra dev
uv run pytest                 # all tests
uv run pytest --cov=ethics_canvas
```

## Security

- Per-IP rate limiting in the app (10/min deliberation, 30/min follow-up)
- Cloudflare WAF rules at the edge
- Hardened systemd unit (ProtectSystem=strict, ProtectHome=read-only, etc.)
- UFW + fail2ban on the VPS
- Origin IP not exposed (Cloudflare Tunnel only)
- See [SECURITY.md](SECURITY.md) for how to report a vulnerability

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). The short version: fork, branch, run tests, PR.

## License

[MIT](LICENSE)
