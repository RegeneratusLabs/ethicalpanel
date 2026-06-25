"""FastAPI app: routes, request/response models, error mapping, logging,
rate limiting, and audit logging.

Routes:
- GET  /                  serves static/index.html
- GET  /api/agents        the 8 agent personas as a JSON array
- POST /api/deliberate    SSE: streams 8 agent_result events + complete
- POST /api/follow-up     SSE: streams 1 agent_result event + complete
- GET  /api/health        liveness probe

Security posture (defence in depth):
- System prompt explicitly resists prompt injection from user input
- Per-IP token-bucket rate limit on LLM routes (cost + spam mitigation)
- Audit log records request metadata (IP, UA, prompt hash, latency, verdict)
  but never the full prompt or response (PII + log bloat mitigation)
- Error responses to clients are sanitised; full details only in server logs
- Control characters in user prompts are stripped before the LLM call
"""
from __future__ import annotations
import hashlib
import json
import logging
import re
import time
from collections import defaultdict, deque
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

from ethics_canvas.agents import AGENTS, AGENT_ORDER
from ethics_canvas.config import Settings, get_settings
from ethics_canvas.evaluator import (
    AgentResult,
    stream_deliberation,
    stream_follow_up,
    stream_summary,
)
from ethics_canvas.llm import LLMClient, LLMError


log = logging.getLogger("ethics_canvas.api")
audit = logging.getLogger("ethics_canvas.audit")

STATIC_DIR = Path(__file__).parent.parent / "static"

app = FastAPI(title="Ethical Panel")

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# CORS — public API, no credentials. Tighten if auth is added later.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
    max_age=3600,
)


# ---------- Security helpers ----------

# Control characters except common whitespace (tab, newline, carriage return).
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _sanitize_prompt(prompt: str) -> str:
    """Strip control characters and normalise whitespace. Cap to a hard limit."""
    cleaned = _CONTROL_CHARS.sub("", prompt)
    # Collapse runs of spaces/tabs on the same line but preserve newlines.
    cleaned = re.sub(r"[^\S\n]+", " ", cleaned)
    return cleaned.strip()


def _client_ip(request: Request) -> str:
    """Return the client IP, preferring the first X-Forwarded-For hop if present
    behind a trusted proxy. Cloudflare sets CF-Connecting-IP."""
    if (cf := request.headers.get("cf-connecting-ip")):
        return cf.strip()
    if (xff := request.headers.get("x-forwarded-for")):
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _prompt_hash(prompt: str) -> str:
    """Short, non-reversible fingerprint of a prompt for audit logs."""
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:12]


class _RateLimiter:
    """Per-key sliding-window rate limiter. In-memory; single-process only.

    For multi-worker deployments swap for slowapi or a Redis backend.
    """

    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._buckets: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str) -> tuple[bool, int]:
        now = time.monotonic()
        bucket = self._buckets[key]
        # Drop entries that have aged out of the window.
        while bucket and now - bucket[0] > self.window_seconds:
            bucket.popleft()
        if len(bucket) >= self.max_requests:
            retry_after = int(self.window_seconds - (now - bucket[0])) + 1
            return False, max(retry_after, 1)
        bucket.append(now)
        return True, 0


# Deliberations are expensive (~8s + LLM tokens); follow-ups are cheaper.
_deliberate_limiter = _RateLimiter(max_requests=10, window_seconds=60)
_followup_limiter = _RateLimiter(max_requests=30, window_seconds=60)


def _enforce_rate_limit(request: Request, limiter: _RateLimiter) -> None:
    allowed, retry_after = limiter.check(_client_ip(request))
    if not allowed:
        log.warning("rate limit hit ip=%s path=%s retry_after=%ds",
                    _client_ip(request), request.url.path, retry_after)
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Retry after {retry_after}s.",
            headers={"Retry-After": str(retry_after)},
        )


def _rate_limit_deliberate(request: Request) -> None:
    _enforce_rate_limit(request, _deliberate_limiter)


def _rate_limit_followup(request: Request) -> None:
    _enforce_rate_limit(request, _followup_limiter)


def get_llm(settings: Settings = Depends(get_settings)) -> LLMClient:
    import json
    thinking = None
    if settings.deepseek_thinking.strip():
        thinking = json.loads(settings.deepseek_thinking)
    return LLMClient(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        model=settings.deepseek_model,
        timeout=settings.request_timeout_s,
        thinking=thinking,
    )


# ---------- Request/response models ----------

class DeliberateRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=5000)

    @field_validator("prompt")
    @classmethod
    def _prompt_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("prompt must not be empty")
        return v


class ContextMessage(BaseModel):
    role: str
    content: str
    agent_id: str | None = None


class FollowUpRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=5000)
    agent_id: str = Field(..., min_length=1)
    context: list[ContextMessage] = Field(default_factory=list)

    @field_validator("agent_id")
    @classmethod
    def _agent_known(cls, v: str) -> str:
        if v not in AGENTS:
            raise ValueError(f"unknown agent id: {v!r}")
        return v

    @field_validator("prompt")
    @classmethod
    def _prompt_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("prompt must not be empty")
        return v


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.monotonic()
    response = await call_next(request)
    latency_ms = int((time.monotonic() - start) * 1000)
    log.info(
        "%s %s status=%d latency_ms=%d",
        request.method, request.url.path, response.status_code, latency_ms,
    )
    return response


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/agents")
def list_agents() -> list[dict]:
    return [
        {"id": a.id, "name": a.name, "focus": a.focus, "color": a.color}
        for a in (AGENTS[aid] for aid in AGENT_ORDER)
    ]


@app.get("/")
def serve_index():
    index_path = STATIC_DIR / "index.html"
    if not index_path.exists():
        return HTMLResponse(
            "<!DOCTYPE html><html><head><title>Ethical Panel</title></head>"
            "<body><h1>Ethical Panel</h1>"
            "<p>Frontend not yet built.</p></body></html>"
        )
    return FileResponse(index_path, media_type="text/html")


def _sse_format(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@app.post("/api/deliberate")
async def deliberate(
    req: DeliberateRequest,
    request: Request,
    llm: LLMClient = Depends(get_llm),
    _: None = Depends(_rate_limit_deliberate),
) -> StreamingResponse:
    prompt = _sanitize_prompt(req.prompt)
    ip = _client_ip(request)
    ph = _prompt_hash(prompt)
    audit.info("event=deliberate_start ip=%s ua=%s prompt_hash=%s prompt_len=%d",
               ip, request.headers.get("user-agent", "-"), ph, len(prompt))
    start = time.monotonic()
    verdict = None
    agent_count = 0

    async def event_gen():
        nonlocal verdict, agent_count
        results: list[AgentResult] = []
        try:
            async for event in stream_deliberation(prompt, llm=llm):
                etype = event["type"]
                if etype == "agent_start":
                    yield _sse_format("agent_start", {"id": event["id"]})
                elif etype == "reasoning_delta":
                    yield _sse_format("reasoning_delta", {
                        "id": event["id"],
                        "text": event["text"],
                    })
                elif etype == "agent_result":
                    result = event["result"]
                    results.append(result)
                    agent_count += 1
                    yield _sse_format("agent_result", {
                        "id": result.id,
                        "score": result.score,
                        "verdict": result.verdict.value,
                        "flags": result.flags,
                        "reasoning": result.reasoning,
                    })
            # Aggregate verdict (same logic the frontend uses).
            passes = sum(1 for r in results if r.verdict.value == "pass")
            flags = sum(1 for r in results if r.verdict.value == "flag")
            verdict = "pass" if passes >= 4 else "flag" if flags >= 3 else "caution"
            yield _sse_format("complete", {
                "results": [
                    {
                        "id": r.id, "score": r.score,
                        "verdict": r.verdict.value, "flags": r.flags,
                        "reasoning": r.reasoning,
                    }
                    for r in results
                ],
            })
            # Post-deliberation summary (optional 9th LLM call). The summary
            # streams in after the verdict; if it fails, the agents'
            # results are unaffected and we surface a soft error.
            if results:
                try:
                    async for sev in stream_summary(prompt, results, llm=llm):
                        stype = sev["type"]
                        if stype == "summary_start":
                            yield _sse_format("summary_start", {})
                        elif stype == "summary_delta":
                            yield _sse_format("summary_delta", {"text": sev["text"]})
                        elif stype == "summary_result":
                            yield _sse_format("summary_result", {"text": sev["text"]})
                except LLMError as e:
                    log.warning("summary failed (agents succeeded): %s", e.message)
                    yield _sse_format("summary_error", {"message": e.message})
                except Exception:  # noqa: BLE001
                    log.exception("summary unexpected error")
                    yield _sse_format("summary_error", {"message": "internal error"})
        except LLMError as e:
            log.warning("deliberate failed: %s", e.message)
            yield _sse_format("error", {"message": e.message})
        except Exception:  # noqa: BLE001
            log.exception("deliberate unexpected error")
            yield _sse_format("error", {"message": "internal error"})
        finally:
            audit.info(
                "event=deliberate_end ip=%s prompt_hash=%s latency_ms=%d "
                "agent_count=%d verdict=%s",
                ip, ph, int((time.monotonic() - start) * 1000),
                agent_count, verdict or "error",
            )

    return StreamingResponse(event_gen(), media_type="text/event-stream")


@app.post("/api/follow-up")
async def follow_up(
    req: FollowUpRequest,
    request: Request,
    llm: LLMClient = Depends(get_llm),
    _: None = Depends(_rate_limit_followup),
) -> StreamingResponse:
    prompt = _sanitize_prompt(req.prompt)
    ip = _client_ip(request)
    ph = _prompt_hash(prompt)
    audit.info("event=follow_up_start ip=%s ua=%s agent_id=%s prompt_hash=%s",
               ip, request.headers.get("user-agent", "-"), req.agent_id, ph)
    start = time.monotonic()
    success = False

    context_dicts = [m.model_dump(exclude_none=True) for m in req.context]
    async def event_gen():
        nonlocal success
        try:
            async for event in stream_follow_up(
                follow_up_text=prompt,
                agent_id=req.agent_id,
                context=context_dicts,
                llm=llm,
            ):
                etype = event["type"]
                if etype == "agent_start":
                    yield _sse_format("agent_start", {"id": event["id"]})
                elif etype == "reasoning_delta":
                    yield _sse_format("reasoning_delta", {
                        "id": event["id"],
                        "text": event["text"],
                    })
                elif etype == "agent_result":
                    result = event["result"]
                    yield _sse_format("agent_result", {
                        "id": result.id,
                        "score": result.score,
                        "verdict": result.verdict.value,
                        "flags": result.flags,
                        "reasoning": result.reasoning,
                    })
            success = True
            yield _sse_format("complete", {"agent_id": req.agent_id})
        except LLMError as e:
            log.warning("follow_up failed: %s", e.message)
            yield _sse_format("error", {"message": e.message})
        except Exception:  # noqa: BLE001
            log.exception("follow_up unexpected error")
            yield _sse_format("error", {"message": "internal error"})
        finally:
            audit.info(
                "event=follow_up_end ip=%s agent_id=%s prompt_hash=%s "
                "latency_ms=%d success=%s",
                ip, req.agent_id, ph,
                int((time.monotonic() - start) * 1000), success,
            )

    return StreamingResponse(event_gen(), media_type="text/event-stream")
