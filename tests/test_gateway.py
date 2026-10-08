import asyncio
from dataclasses import replace

import httpx
import pytest
from fastapi.testclient import TestClient

from app.gateway import Settings, create_app

BASE = Settings(api_key="test-key")
PAYLOAD = {"model": "demo-model", "messages": [{"role": "user", "content": "private prompt"}], "max_tokens": 8}
AUTH = {"Authorization": "Bearer test-key"}


def backend(request):
    if request.url.path == "/health":
        return httpx.Response(200)
    return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})


def client(settings=BASE, handler=backend):
    return TestClient(create_app(settings, httpx.MockTransport(handler)))


def test_auth_fail_closed():
    with pytest.raises(ValueError):
        create_app(Settings())
    with client() as c:
        assert c.post("/v1/chat/completions", json=PAYLOAD).status_code == 401
        assert c.post("/v1/chat/completions", json=PAYLOAD, headers=AUTH).status_code == 200


@pytest.mark.parametrize(
    "patch",
    [
        {"stream": True},
        {"messages": []},
        {"model": "other"},
        {"max_tokens": 99999},
        {"max_tokens": True},
        {"messages": [{"role": "user", "content": {}}]},
    ],
)
def test_validation(patch):
    with client() as c:
        assert c.post("/v1/chat/completions", headers=AUTH, json=PAYLOAD | patch).status_code == 400


def test_body_limit_and_bad_json():
    with client(replace(BASE, max_body_bytes=256)) as c:
        assert c.post("/v1/chat/completions", headers=AUTH, content="x" * 257).status_code == 413
        assert c.post("/v1/chat/completions", headers=AUTH, content="{").status_code == 400


def test_upstream_failure_and_readiness():
    with client(handler=lambda _: httpx.Response(503)) as c:
        assert c.get("/health/live").status_code == 200
        assert c.get("/health/ready").status_code == 503
        assert c.post("/v1/chat/completions", headers=AUTH, json=PAYLOAD).status_code == 502
        assert 'outcome="upstream_error"' in c.get("/metrics").text


def test_malformed_backend_is_not_success():
    with client(handler=lambda _: httpx.Response(200, json={"error": "bad"})) as c:
        assert c.post("/v1/chat/completions", headers=AUTH, json=PAYLOAD).status_code == 502


def test_metrics_and_logs_do_not_contain_prompt(caplog):
    with client() as c, caplog.at_level("INFO", logger="modelops"):
        response = c.post("/v1/chat/completions", headers=AUTH, json=PAYLOAD)
        assert len(response.headers["x-request-id"]) == 32
        metrics = c.get("/metrics").text
        assert 'modelops_requests_total{outcome="success"} 1.0' in metrics
        assert "private prompt" not in metrics + caplog.text
        assert "test-key" not in caplog.text


def test_concurrency_rejection_and_capacity_recovery():
    async def scenario():
        entered, release = asyncio.Event(), asyncio.Event()

        async def slow(_):
            entered.set()
            await release.wait()
            return backend(_)

        app = create_app(replace(BASE, max_inflight=1), httpx.MockTransport(slow))
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
                first = asyncio.create_task(c.post("/v1/chat/completions", headers=AUTH, json=PAYLOAD))
                await entered.wait()
                second = await c.post("/v1/chat/completions", headers=AUTH, json=PAYLOAD)
                assert second.status_code == 429
                assert second.headers["retry-after"] == "1"
                release.set()
                assert (await first).status_code == 200
                assert (await c.post("/v1/chat/completions", headers=AUTH, json=PAYLOAD)).status_code == 200

    asyncio.run(scenario())


def test_deadline_releases_capacity():
    async def slow(_):
        await asyncio.sleep(0.1)
        return backend(_)

    with client(replace(BASE, timeout_seconds=0.01, max_inflight=1), slow) as c:
        for _ in range(2):
            assert c.post("/v1/chat/completions", headers=AUTH, json=PAYLOAD).status_code == 504
        assert "modelops_inflight 0.0" in c.get("/metrics").text
