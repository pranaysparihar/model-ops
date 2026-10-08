"""Closed-loop load sample. Measures full-response latency, never model quality/TTFT."""

import argparse
import concurrent.futures
import json
import os
import statistics
import time
import urllib.error
import urllib.request
from collections import Counter

parser = argparse.ArgumentParser()
parser.add_argument("--requests", type=int, default=100)
parser.add_argument("--concurrency", type=int, default=8)
args = parser.parse_args()
if args.requests < 1 or args.concurrency < 1:
    parser.error("requests and concurrency must be positive")
url = os.getenv("BASE_URL", "http://127.0.0.1:8080")
key = os.environ["API_KEY"]


def call(_):
    started = time.monotonic()
    data = json.dumps(
        {
            "model": os.getenv("MODEL", "demo-model"),
            "messages": [{"role": "user", "content": "Say hello"}],
            "max_tokens": 16,
        }
    ).encode()
    req = urllib.request.Request(
        url + "/v1/chat/completions",
        data=data,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=70) as response:
            response.read()
            status = str(response.status)
    except urllib.error.HTTPError as error:
        status = str(error.code)
    except (OSError, TimeoutError):
        status = "transport_error"
    return status, time.monotonic() - started


start = time.monotonic()
with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
    results = list(pool.map(call, range(args.requests)))
latencies = sorted(t for status, t in results if status == "200")
print(
    json.dumps(
        {
            "workload": "closed-loop fixed short text, max_tokens=16",
            "requests": args.requests,
            "concurrency": args.concurrency,
            "elapsed_seconds": round(time.monotonic() - start, 3),
            "statuses": dict(Counter(s for s, _ in results)),
            "successful_completion_p50_seconds": statistics.median(latencies) if latencies else None,
            "successful_completion_p95_seconds": latencies[min(len(latencies) - 1, int(len(latencies) * 0.95))]
            if latencies
            else None,
        },
        indent=2,
    )
)
