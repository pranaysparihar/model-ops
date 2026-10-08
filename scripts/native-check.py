"""Exercise real HTTP servers and dependency recovery without Docker or a GPU."""

import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request


def port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def request(url, data=None, key=None):
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    req = urllib.request.Request(url, data=json.dumps(data).encode() if data else None, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=3) as response:
            return response.status, response.read().decode()
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode()


backend_port, gateway_port = port(), port()
base = f"http://127.0.0.1:{gateway_port}"
processes = []
checks = []
Path("artifacts").mkdir(exist_ok=True)
with tempfile.TemporaryDirectory() as directory, open("artifacts/native-server.log", "w") as log:
    fault = Path(directory) / "failed"
    env = os.environ | {
        "API_KEY": "ephemeral-test-key",
        "BACKEND_URL": f"http://127.0.0.1:{backend_port}",
        "FAULT_FILE": str(fault),
    }
    try:
        for app, bind_port, factory in [
            ("app.simulator:app", backend_port, []),
            ("app.gateway:create_app", gateway_port, ["--factory"]),
        ]:
            processes.append(
                subprocess.Popen(
                    [
                        sys.executable,
                        "-m",
                        "uvicorn",
                        app,
                        *factory,
                        "--host",
                        "127.0.0.1",
                        "--port",
                        str(bind_port),
                        "--no-access-log",
                    ],
                    env=env,
                    stdout=log,
                    stderr=log,
                )
            )
        for _ in range(100):
            try:
                if request(base + "/health/ready")[0] == 200:
                    break
            except OSError:
                pass
            time.sleep(0.1)
        else:
            raise AssertionError("HTTP servers failed to become ready")
        payload = {"messages": [{"role": "user", "content": "Test"}], "max_tokens": 16}
        assert request(base + "/v1/chat/completions", payload)[0] == 401
        checks.append("anonymous completion rejected")
        status, body = request(base + "/v1/chat/completions", payload, env["API_KEY"])
        assert status == 200 and "not model inference" in body
        checks.append("authenticated simulator completion returned")
        fault.touch()
        assert request(base + "/health/live")[0] == 200
        assert request(base + "/health/ready")[0] == 503
        assert request(base + "/v1/chat/completions", payload, env["API_KEY"])[0] == 502
        checks.append("dependency failure removes readiness without killing gateway")
        fault.unlink()
        assert request(base + "/health/ready")[0] == 200
        assert request(base + "/v1/chat/completions", payload, env["API_KEY"])[0] == 200
        checks.append("dependency recovery restores service")
        metrics = request(base + "/metrics")[1]
        assert 'modelops_requests_total{outcome="upstream_error"} 1.0' in metrics
        checks.append("failure recorded in Prometheus metrics")
        report = {"backend": "deterministic CPU simulator; no model inference", "checks": checks, "result": "passed"}
        Path("artifacts/native-check.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))
    finally:
        for process in processes:
            process.terminate()
        for process in processes:
            process.wait(timeout=10)
