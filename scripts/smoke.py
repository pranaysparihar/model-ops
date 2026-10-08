"""Authenticated functional smoke test; exits non-zero on broken completions."""

import json
import os
import sys
import urllib.request

url = os.getenv("BASE_URL", "http://127.0.0.1:8080")
key = os.environ["API_KEY"]
model = os.getenv("MODEL", "demo-model")
try:
    with urllib.request.urlopen(url + "/health/ready", timeout=5) as response:
        assert response.status == 200
    req = urllib.request.Request(
        url + "/v1/chat/completions",
        data=json.dumps(
            {
                "model": model,
                "messages": [{"role": "user", "content": "Reply with a short greeting."}],
                "max_tokens": 16,
            }
        ).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=70) as response:
        body = json.load(response)
        assert isinstance(body["choices"][0]["message"]["content"], str)
    print("PASS: backend ready and authenticated completion returned")
except Exception as error:
    print(f"FAIL: {type(error).__name__}: {error}", file=sys.stderr)
    sys.exit(1)
