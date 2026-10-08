"""Bounded, observable proxy for a non-streaming OpenAI-compatible backend."""

import asyncio
import hmac
import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, generate_latest

log = logging.getLogger("modelops")
logging.basicConfig(level=logging.INFO, format="%(message)s")


@dataclass(frozen=True)
class Settings:
    backend_url: str = "http://127.0.0.1:8001"
    api_key: str = ""
    backend_key: str = ""
    model: str = "demo-model"
    max_inflight: int = 4
    timeout_seconds: float = 10
    max_body_bytes: int = 65536
    max_tokens: int = 256

    @classmethod
    def from_env(cls):
        return cls(
            backend_url=os.getenv("BACKEND_URL", "http://127.0.0.1:8001"),
            api_key=os.getenv("API_KEY", ""),
            backend_key=os.getenv("BACKEND_API_KEY", ""),
            model=os.getenv("MODEL", "demo-model"),
            max_inflight=int(os.getenv("MAX_INFLIGHT", "4")),
            timeout_seconds=float(os.getenv("UPSTREAM_TIMEOUT_SECONDS", "10")),
            max_body_bytes=int(os.getenv("MAX_BODY_BYTES", "65536")),
            max_tokens=int(os.getenv("MAX_TOKENS", "256")),
        )


def create_app(settings=None, transport=None):
    cfg = settings or Settings.from_env()
    if not cfg.api_key:
        raise ValueError("API_KEY must be set; anonymous inference is disabled")
    if min(cfg.max_inflight, cfg.timeout_seconds, cfg.max_body_bytes, cfg.max_tokens) <= 0:
        raise ValueError("Capacity, timeout, body and token limits must be positive")
    registry = CollectorRegistry()
    requests = Counter(
        "modelops_requests_total", "Completion requests by bounded outcome", ["outcome"], registry=registry
    )
    duration = Histogram(
        "modelops_request_duration_seconds",
        "Full completion latency (not TTFT)",
        ["outcome"],
        buckets=(0.1, 0.25, 0.5, 1, 2, 5, 10, 30, 60),
        registry=registry,
    )
    inflight = Gauge("modelops_inflight", "Active upstream requests per gateway replica", registry=registry)
    for outcome in ("success", "upstream_error", "timeout", "overloaded", "invalid", "unauthorized"):
        requests.labels(outcome)
        duration.labels(outcome)
    active = 0

    @asynccontextmanager
    async def lifespan(app):
        headers = {"Authorization": f"Bearer {cfg.backend_key}"} if cfg.backend_key else {}
        async with httpx.AsyncClient(
            base_url=cfg.backend_url,
            timeout=cfg.timeout_seconds,
            headers=headers,
            transport=transport,
            limits=httpx.Limits(max_connections=cfg.max_inflight + 2),
        ) as client:
            app.state.client = client
            yield

    app = FastAPI(title="ModelOps gateway", lifespan=lifespan, docs_url=None, redoc_url=None)

    @app.middleware("http")
    async def record(request: Request, call_next):
        start = time.monotonic()
        request.state.request_id = uuid.uuid4().hex
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        if request.url.path == "/v1/chat/completions":
            outcome = getattr(request.state, "outcome", "invalid")
            elapsed = time.monotonic() - start
            requests.labels(outcome).inc()
            duration.labels(outcome).observe(elapsed)
            # Never log prompts, completions, authorization headers, or caller IDs.
            log.info(
                json.dumps(
                    {
                        "request_id": request.state.request_id,
                        "outcome": outcome,
                        "status": response.status_code,
                        "duration_seconds": round(elapsed, 4),
                    }
                )
            )
        return response

    @app.get("/health/live")
    async def live():
        return {"status": "alive"}

    @app.get("/health/ready")
    async def ready():
        try:
            response = await app.state.client.get("/health", timeout=2)
            response.raise_for_status()
            return {"status": "ready"}
        except httpx.HTTPError:
            return JSONResponse({"status": "backend_unavailable"}, status_code=503)

    @app.get("/metrics")
    async def metrics():
        return Response(generate_latest(registry), media_type="text/plain; version=0.0.4")

    @app.post("/v1/chat/completions")
    async def completion(request: Request):
        nonlocal active

        def error(status, outcome, message):
            request.state.outcome = outcome
            return JSONResponse(
                {"error": {"message": message, "type": outcome}},
                status_code=status,
                headers={"Retry-After": "1"} if status == 429 else None,
            )

        if not hmac.compare_digest(request.headers.get("authorization", "").encode(), f"Bearer {cfg.api_key}".encode()):
            return error(401, "unauthorized", "Invalid API key")
        body = bytearray()
        try:
            async with asyncio.timeout(5):
                async for chunk in request.stream():
                    body.extend(chunk)
                    if len(body) > cfg.max_body_bytes:
                        return error(413, "invalid", "Request body too large")
        except TimeoutError:
            return error(408, "invalid", "Request body timeout")
        try:
            payload = json.loads(body)
            if not isinstance(payload, dict):
                raise ValueError()
            messages = payload.get("messages")
            tokens = payload.get("max_tokens", cfg.max_tokens)
            if payload.get("stream", False) is not False:
                raise ValueError("Streaming is not supported in this release")
            if not isinstance(messages, list) or not messages or len(messages) > 100:
                raise ValueError()
            if any(
                not isinstance(m, dict)
                or m.get("role") not in ("system", "user", "assistant")
                or not isinstance(m.get("content"), str)
                for m in messages
            ):
                raise ValueError()
            if isinstance(tokens, bool) or not isinstance(tokens, int) or not 1 <= tokens <= cfg.max_tokens:
                raise ValueError()
            if payload.get("model", cfg.model) != cfg.model:
                raise ValueError()
        except (ValueError, TypeError):
            return error(
                400, "invalid", "Use the configured model, text messages, bounded max_tokens, and stream=false"
            )
        # One event loop and one worker per replica: no await between check/increment.
        if active >= cfg.max_inflight:
            return error(429, "overloaded", "Gateway capacity reached; retry with backoff")
        active += 1
        inflight.inc()
        try:
            # Hard overall deadline, not only per-socket inactivity timeout.
            async with asyncio.timeout(cfg.timeout_seconds):
                response = await app.state.client.post(
                    "/v1/chat/completions",
                    json={"model": cfg.model, "messages": messages, "max_tokens": tokens, "stream": False},
                )
                response.raise_for_status()
                data = response.json()
                if not isinstance(data, dict) or not isinstance(data.get("choices"), list) or not data["choices"]:
                    raise ValueError("Malformed backend response")
            request.state.outcome = "success"
            return JSONResponse(data)
        except (TimeoutError, httpx.TimeoutException):
            return error(504, "timeout", "Backend deadline exceeded")
        except (httpx.HTTPError, ValueError):
            return error(502, "upstream_error", "Backend request failed")
        finally:
            active -= 1
            inflight.dec()

    return app
