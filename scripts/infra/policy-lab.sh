#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
cluster=modelops-policy
if kind get clusters | grep -qx "$cluster"; then
  echo "Refusing to replace existing cluster $cluster. Delete it explicitly before rerunning."
  exit 1
fi
# Isolate credentials/context selection from the operator's existing kubeconfig.
export KUBECONFIG
KUBECONFIG=$(mktemp)
cleanup() {
  if [[ "${KEEP_LAB:-0}" != 1 ]]; then
    kind delete cluster --name "$cluster"
    rm -f "$KUBECONFIG"
  else
    echo "Retained lab kubeconfig: $KUBECONFIG"
  fi
}
trap cleanup EXIT
kind create cluster --name "$cluster" --image kindest/node:v1.35.0 --config deploy/kind-policy.yaml
helm upgrade --install cilium cilium --repo https://helm.cilium.io --version 1.20.2 \
  --namespace kube-system --kube-context "kind-$cluster" \
  --set ipam.mode=kubernetes --set operator.replicas=1 --wait --timeout 5m
kubectl --context "kind-$cluster" wait --for=condition=Ready nodes --all --timeout=120s
docker build -t modelops:local .
kind load docker-image modelops:local --name "$cluster"
helm template platform platform --set monitoring.enabled=false --show-only templates/tenant.yaml | kubectl --context "kind-$cluster" apply -f -
python3 scripts/infra/policy-check.py
