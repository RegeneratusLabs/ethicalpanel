# Contributing

Thanks for your interest in improving Ethical Panel. This project is small, opinionated, and open to good-faith contributions.

## Ways to contribute

- **Bug reports**: open an issue with the `bug` label. Include the query, the agents that misbehaved, and what you expected.
- **Feature requests**: open an issue with the `enhancement` label. Explain the use case, not just the implementation.
- **Agent design**: each of the 8 agents has a `constitution` (system prompt) in `ethics_canvas/agents.py`. If an agent gives bad advice on a topic, the fix is usually in the constitution.
- **PRs**: bug fixes, doc improvements, tests, and small UX changes. Big architectural changes — open an issue first.

## Local dev setup

```bash
# Clone your fork
git clone https://github.com/<your-username>/ethicalpanel.git
cd ethicalpanel

# Install deps (Python 3.13 via uv)
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync --extra dev

# Configure (you'll need a DeepSeek API key for the smoke test)
cp .env.example .env
# Edit .env, add DEEPSEEK_API_KEY
chmod 600 .env

# Run tests
uv run pytest

# Run the app
bash start.sh
# Open http://localhost:8001
```

## Code conventions

- **Python 3.13**, no type stubs required but type hints are welcome
- **No new dependencies** without discussion. The runtime deps are intentionally tiny (FastAPI, uvicorn, httpx, pydantic). If you need more, justify it in the PR.
- **Frontend**: vanilla JS in a single `static/index.html`. No build step, no framework, no bundler. CSS variables for theming.
- **No secrets in code**. Tests that hit the real LLM use the `DEEPSEEK_API_KEY` env var.

## Testing

- 8 test files, ~80 tests, all in `tests/`
- `pytest` for everything; the smoke test against the real LLM is gated on `DEEPSEEK_API_KEY`
- A PR should add a test for the bug being fixed or the feature being added. If your change is hard to test, explain why in the PR.

## Pull request process

1. Fork and create a branch (`git checkout -b fix/issue-N-short-name`)
2. Make your change, add tests, run the full suite
3. Commit with a clear message (`fix:`, `feat:`, `docs:`, `chore:` prefixes)
4. Push and open a PR against `main`
5. Wait for review. Small PRs (< 200 lines) get reviewed fastest.

## Code of conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md). Be kind. Assume good faith. Argue ideas, not people.

## License

By contributing, you agree your contributions will be licensed under the [MIT License](LICENSE).
