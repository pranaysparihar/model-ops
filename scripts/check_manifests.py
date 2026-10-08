"""Fail CI on deployment configuration that weakens the lab's core guarantees."""

import sys
import yaml

for filename in sys.argv[1:]:
    manifests = [d for d in yaml.safe_load_all(open(filename)) if d]
    assert manifests, f"Empty manifest: {filename}"
    for doc in manifests:
        if doc["kind"] == "Deployment":
            spec = doc["spec"]["template"]["spec"]
            assert spec["automountServiceAccountToken"] is False
            for container in spec["containers"]:
                assert container["resources"]["requests"]
                assert container["resources"]["limits"]
                assert ":latest" not in container["image"]
                assert container["securityContext"]["allowPrivilegeEscalation"] is False
            if doc["metadata"]["name"].endswith("-gateway"):
                container = spec["containers"][0]
                assert container["readinessProbe"]["httpGet"]["path"] == "/health/ready"
                assert container["livenessProbe"]["httpGet"]["path"] == "/health/live"
                assert doc["spec"]["strategy"]["rollingUpdate"]["maxUnavailable"] == 0
    print(f"PASS: {filename}")
