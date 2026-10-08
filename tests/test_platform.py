"""Render the real composition chart; check cross-component operational contracts."""
import subprocess

import pytest
import yaml


SHA = "1" * 40
DIGEST = "sha256:" + "2" * 64
CLOUD = ["cloud.enabled=true", "cloud.clusterName=test", "cloud.clusterEndpoint=https://test.invalid",
         "cloud.nodeRole=test-role", "cloud.interruptionQueue=test-queue", "cloud.gatewaySecretArn=arn:test"]
GPU = [*CLOUD, "gpu.enabled=true", "gpu.amiID=ami-0123456789abcdef0"]


def render(*values, success=True):
    args = ["helm", "template", "platform", "platform"]
    for value in values:
        args += ["--set", value]
    result = subprocess.run(args, text=True, capture_output=True)
    if not success:
        assert result.returncode != 0
        return result.stderr
    assert result.returncode == 0, result.stderr
    return [d for d in yaml.safe_load_all(result.stdout) if d]


def find(docs, kind, name):
    return next(d for d in docs if d["kind"] == kind and d["metadata"]["name"] == name)


def test_default_cannot_provision_gpu_or_deploy_workload():
    docs = render()
    assert not any(d["kind"] in {"NodePool", "EC2NodeClass", "ExternalSecret"} for d in docs)
    assert not any(d["metadata"]["name"] == "modelops-inference" for d in docs)
    namespace = find(docs, "Namespace", "modelops")
    assert namespace["metadata"]["labels"]["pod-security.kubernetes.io/enforce"] == "restricted"


def test_gpu_capacity_and_driver_ownership():
    docs = render(*GPU)
    pool = find(docs, "NodePool", "modelops-gpu")["spec"]
    assert pool["limits"]["nvidia.com/gpu"] == "1"
    assert pool["disruption"]["consolidationPolicy"] == "WhenEmpty"
    assert pool["template"]["spec"]["taints"][0]["value"] == "gpu"
    node = find(docs, "EC2NodeClass", "modelops-gpu")["spec"]
    assert node["amiSelectorTerms"] == [{"id": "ami-0123456789abcdef0"}]
    assert node["metadataOptions"]["httpTokens"] == "required"
    operator = find(docs, "Application", "modelops-gpu-operator")["spec"]["source"]["helm"]["valuesObject"]
    assert operator["driver"]["enabled"] is False
    assert operator["toolkit"]["enabled"] is False
    assert operator["node-feature-discovery"]["worker"]["tolerations"][0]["value"] == "gpu"


def test_workload_promotion_is_digest_pinned_and_manual():
    docs = render(*GPU, "workload.enabled=true", f"workload.imageTag={SHA}", f"workload.imageDigest={DIGEST}")
    app = find(docs, "Application", "modelops-inference")["spec"]
    assert app["source"]["targetRevision"] == SHA
    values = app["source"]["helm"]["valuesObject"]
    assert values["image"]["digest"] == DIGEST
    assert values["backend"]["storageClassName"] == "modelops-gp3"
    assert "automated" not in app["syncPolicy"]
    project = find(docs, "AppProject", "modelops-workloads")["spec"]
    assert project["clusterResourceWhitelist"] == []
    assert {d["namespace"] for d in project["destinations"]} == {"modelops"}


@pytest.mark.parametrize("settings", [
    ["gpu.enabled=true"],
    [*CLOUD, "gpu.enabled=true"],
    ["workload.enabled=true", "workload.imageTag=latest"],
    ["workload.enabled=true", f"workload.imageTag={SHA}"],
    ["gpu.limit=0"],
    ["workload.replicas=2"],
])
def test_invalid_or_incomplete_capacity_changes_fail_closed(settings):
    render(*settings, success=False)


def test_secret_scope_and_monitoring_ingress_are_explicit():
    docs = render(*GPU)
    secret = find(docs, "ExternalSecret", "modelops-api-key")["spec"]
    assert secret["data"][0]["remoteRef"]["key"] == "arn:test"
    deny = find(docs, "NetworkPolicy", "default-deny-ingress")["spec"]
    assert deny == {"podSelector": {}, "policyTypes": ["Ingress"]}
    ingress = find(docs, "NetworkPolicy", "gateway-ingress")["spec"]["ingress"][0]
    namespaces = {r["namespaceSelector"]["matchLabels"]["kubernetes.io/metadata.name"] for r in ingress["from"]}
    assert namespaces == {"monitoring", "ingress-system"}
