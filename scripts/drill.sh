#!/usr/bin/env bash
# Destructive experiments are restricted to our disposable kind cluster.
set -euo pipefail
cd "$(dirname "$0")/.."
export KUBE_CONTEXT=kind-modelops-lab
export NAMESPACE=modelops RELEASE=modelops
set -a
source .env
set +a
kubectl --context "$KUBE_CONTEXT" -n modelops rollout status deployment/modelops-gateway --timeout=60s
mkdir -p artifacts
exec > >(tee artifacts/drill.log) 2>&1
echo "Started: $(date -u +%FT%TZ)"
echo 'Exercise 1: a bad image must fail deployment and preserve the working release.'
if IMAGE_TAG=deliberately-missing HELM_TIMEOUT=45s ./scripts/deploy.sh; then
  echo 'FAIL: deliberately broken release unexpectedly succeeded'; exit 1
fi
actual=$(kubectl --context "$KUBE_CONTEXT" -n modelops get deployment modelops-gateway -o jsonpath='{.spec.template.spec.containers[0].image}')
[[ "$actual" == modelops:local ]]
kubectl --context "$KUBE_CONTEXT" -n modelops rollout status deployment/modelops-gateway --timeout=90s
echo 'PASS: bad release restored the original image.'
echo 'Exercise 2: readiness passes but authenticated smoke fails; restore previous revision.'
if API_KEY=deliberately-wrong IMAGE_TAG=local ./scripts/deploy.sh; then
  echo 'FAIL: incorrect verification credential unexpectedly succeeded'; exit 1
fi
helm history modelops --kube-context "$KUBE_CONTEXT" -n modelops -o json | python3 -c 'import json,sys; latest=json.load(sys.stdin)[-1]; assert latest["status"] == "deployed"; assert "Rollback" in latest["description"]'
echo 'PASS: functional failure triggers explicit rollback.'
echo 'Exercise 3: terminate a backend pod and verify replacement plus a real request.' 
old=$(kubectl --context "$KUBE_CONTEXT" -n modelops get pod -l app=modelops-backend -o jsonpath='{.items[0].metadata.uid}')
kubectl --context "$KUBE_CONTEXT" -n modelops delete pod -l app=modelops-backend --wait=true
kubectl --context "$KUBE_CONTEXT" -n modelops rollout status deployment/modelops-backend --timeout=90s
new=$(kubectl --context "$KUBE_CONTEXT" -n modelops get pod -l app=modelops-backend -o jsonpath='{.items[0].metadata.uid}')
[[ "$old" != "$new" ]]
IMAGE_TAG=local ./scripts/deploy.sh
echo 'PASS: backend replaced and completion verified.'
echo "Completed: $(date -u +%FT%TZ)"
