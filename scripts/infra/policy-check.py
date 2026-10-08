"""Exercise admission and network enforcement in ONLY the disposable Cilium lab."""
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

CONTEXT = "kind-modelops-policy"
checks = []


def kubectl(*args, input_doc=None, check=True):
    return subprocess.run(
        ["kubectl", "--context", CONTEXT, *args],
        input=json.dumps(input_doc) if input_doc else None,
        text=True, capture_output=True, check=check,
    )


def apply(doc):
    return kubectl("apply", "-f", "-", input_doc=doc)


def pod(name, namespace, gpu=False):
    resources = {"requests": {"cpu": "10m", "memory": "32Mi"}, "limits": {"cpu": "100m", "memory": "64Mi"}}
    if gpu:
        resources["requests"]["nvidia.com/gpu"] = "1"
        resources["limits"]["nvidia.com/gpu"] = "1"
    return {"apiVersion": "v1", "kind": "Pod", "metadata": {"name": name, "namespace": namespace}, "spec": {
        "automountServiceAccountToken": False,
        "securityContext": {"runAsNonRoot": True, "runAsUser": 10001, "seccompProfile": {"type": "RuntimeDefault"}},
        "containers": [{"name": "probe", "image": "modelops:local", "imagePullPolicy": "Never", "command": ["python", "-c", "import time; time.sleep(3600)"], "resources": resources,
                        "securityContext": {"allowPrivilegeEscalation": False, "readOnlyRootFilesystem": True, "capabilities": {"drop": ["ALL"]}}}],
    }}


for namespace in ["monitoring", "untrusted"]:
    apply({"apiVersion": "v1", "kind": "Namespace", "metadata": {"name": namespace}})
    apply(pod("probe", namespace))
    kubectl("-n", namespace, "wait", "--for=condition=Ready", "pod/probe", "--timeout=120s")
# Disposable test credential; never used outside this cluster.
apply({"apiVersion": "v1", "kind": "Secret", "metadata": {"name": "modelops-api-key", "namespace": "modelops"}, "stringData": {"api-key": "policy-test-only"}})
subprocess.run(["helm", "upgrade", "--install", "modelops", "deploy/chart", "--namespace", "modelops", "--kube-context", CONTEXT, "--wait", "--timeout", "3m"], check=True)

probe_code = """
import socket, sys, urllib.request, urllib.error
try:
    with urllib.request.urlopen(sys.argv[1], timeout=3) as r:
        print(r.status)
        sys.exit(0 if r.status == 200 else 3)
except (TimeoutError, socket.timeout):
    print('TIMEOUT: blocked'); sys.exit(2)
except urllib.error.URLError as e:
    if isinstance(e.reason, (TimeoutError, socket.timeout)):
        print('TIMEOUT: blocked'); sys.exit(2)
    print(type(e.reason).__name__); sys.exit(3)
"""
for namespace, expected in [("monitoring", 0), ("untrusted", 2)]:
    for service, path, port in [("gateway", "/health/live", 8000), ("backend", "/health", 8001)]:
        for _ in range(10):
            result = kubectl("-n", namespace, "exec", "probe", "--", "python", "-c", probe_code, f"http://modelops-{service}.modelops:{port}{path}", check=False)
            if result.returncode == expected:
                break
            time.sleep(2)
        assert result.returncode == expected, (namespace, service, result.stdout, result.stderr)
        checks.append({"check": f"{namespace}-to-{service}", "result": "allowed" if expected == 0 else "blocked-timeout"})

apply(pod("gpu-reservation-one", "modelops", gpu=True))
result = kubectl("apply", "-f", "-", input_doc=pod("gpu-reservation-two", "modelops", gpu=True), check=False)
assert result.returncode != 0 and "exceeded quota" in result.stderr, result.stderr
checks.append({"check": "second-gpu-reservation", "result": "rejected-by-quota"})
kubectl("-n", "modelops", "delete", "pod/gpu-reservation-one", "--wait=false")
unsafe = pod("unsafe", "modelops")
unsafe["spec"]["containers"][0]["securityContext"]["privileged"] = True
unsafe["spec"]["containers"][0]["securityContext"]["allowPrivilegeEscalation"] = True
result = kubectl("create", "--dry-run=server", "-f", "-", input_doc=unsafe, check=False)
assert result.returncode != 0 and "violates PodSecurity" in result.stderr, result.stderr
checks.append({"check": "privileged-workload", "result": "rejected-by-pod-security"})
report = {"timestamp": datetime.now(timezone.utc).isoformat(), "context": CONTEXT, "cni": "Cilium 1.20.2", "gpu_hardware_tested": False, "checks": checks}
Path("artifacts").mkdir(exist_ok=True)
Path("artifacts/policy-evidence.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
