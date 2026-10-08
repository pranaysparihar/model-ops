"""Read-only acceptance evidence from an explicitly selected real GPU cluster.

Run with KUBE_CONTEXT, API_KEY, and BASE_URL (an existing gateway port-forward).
Refuses simulator workloads. Does not provision, scale, or delete anything.
"""
import json
import os
import subprocess
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

context = os.environ["KUBE_CONTEXT"]
base_url = os.environ["BASE_URL"].rstrip("/")
key = os.environ["API_KEY"]


def kube(*args):
    return subprocess.check_output(["kubectl", "--context", context, *args], text=True)


pods = json.loads(kube("-n", "modelops", "get", "pods", "-l", "modelops-role=backend", "-o", "json"))["items"]
ready = [p for p in pods if any(c["type"] == "Ready" and c["status"] == "True" for c in p.get("status", {}).get("conditions", []))]
assert len(ready) == 1, "Expected one ready GPU backend"
pod = ready[0]
container = pod["spec"]["containers"][0]
assert container["resources"]["limits"].get("nvidia.com/gpu") == "1", "Backend is not a GPU workload"
node_name = pod["spec"]["nodeName"]
node = json.loads(kube("get", "node", node_name, "-o", "json"))
assert int(node["status"]["allocatable"].get("nvidia.com/gpu", "0")) >= 1
hardware = kube("-n", "modelops", "exec", pod["metadata"]["name"], "--", "nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader").strip()
assert hardware, "No visible NVIDIA device"
request = urllib.request.Request(base_url + "/v1/chat/completions", data=json.dumps({"model": "Qwen/Qwen2.5-0.5B-Instruct", "messages": [{"role": "user", "content": "Reply with a short greeting."}], "max_tokens": 16}).encode(), headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
with urllib.request.urlopen(request, timeout=70) as response:
    body = json.load(response)
assert body.get("id") != "simulated" and body["choices"][0]["message"]["content"]
report = {"timestamp": datetime.now(timezone.utc).isoformat(), "context": context, "gpu_hardware_tested": True, "node": node_name, "pod_uid": pod["metadata"]["uid"], "hardware": hardware, "image_id": pod["status"]["containerStatuses"][0]["imageID"], "authenticated_completion": "passed", "scope": "single-device readiness and completion, not a benchmark or availability test"}
Path("artifacts").mkdir(exist_ok=True)
Path("artifacts/gpu-acceptance.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
