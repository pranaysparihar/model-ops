#!/usr/bin/env bash
# Deploy to the explicitly selected context. Readiness failures roll back via Helm;
# functional smoke failures restore the previously deployed revision separately.
set -euo pipefail
cd "$(dirname "$0")/.."
: "${KUBE_CONTEXT:?Set KUBE_CONTEXT explicitly}"
: "${IMAGE_TAG:?Set an immutable image tag}"
: "${API_KEY:?Set API_KEY to the existing Kubernetes secret value for smoke verification}"
RELEASE=${RELEASE:-modelops}
NAMESPACE=${NAMESPACE:-modelops}
IMAGE_REPOSITORY=${IMAGE_REPOSITORY:-modelops}
VALUES_FILE=${VALUES_FILE:-deploy/chart/values.yaml}
LOCAL_PORT=${LOCAL_PORT:-18080}
HELM_TIMEOUT=${HELM_TIMEOUT:-5m}
export MODEL=${MODEL:-demo-model}
# Secrets must already exist; deployment never places their values in Helm history.
kubectl --context "$KUBE_CONTEXT" -n "$NAMESPACE" get secret modelops-api-key >/dev/null
prior=$(helm history "$RELEASE" --kube-context "$KUBE_CONTEXT" -n "$NAMESPACE" -o json 2>/dev/null | python3 -c 'import json,sys; a=[x for x in json.loads(sys.stdin.read() or "[]") if x["status"]=="deployed"]; print(a[-1]["revision"] if a else "")' || true)
rollback_flag=--atomic
if [[ $(helm version --short) == v4* ]]; then rollback_flag=--rollback-on-failure; fi
helm upgrade --install "$RELEASE" deploy/chart --kube-context "$KUBE_CONTEXT" -n "$NAMESPACE" -f "$VALUES_FILE" \
  --set-string "image.repository=$IMAGE_REPOSITORY" --set-string "image.tag=$IMAGE_TAG" \
  "$rollback_flag" --wait --timeout "$HELM_TIMEOUT"
kubectl --context "$KUBE_CONTEXT" -n "$NAMESPACE" port-forward "svc/$RELEASE-gateway" "$LOCAL_PORT:8000" >/tmp/modelops-port-forward-$$.log 2>&1 &
pf=$!
cleanup() {
  kill "$pf" 2>/dev/null || true
  wait "$pf" 2>/dev/null || true
  rm -f /tmp/modelops-port-forward-$$.log
}
trap cleanup EXIT
ready=false
for _ in {1..30}; do
  if curl -fsS "http://127.0.0.1:$LOCAL_PORT/health/live" >/dev/null 2>&1; then ready=true; break; fi
  sleep 1
done
if [[ "$ready" == true ]] && BASE_URL="http://127.0.0.1:$LOCAL_PORT" python3 scripts/smoke.py; then
  echo 'Release passed functional verification.'
else
  if [[ -n "$prior" ]]; then
    helm rollback "$RELEASE" "$prior" --kube-context "$KUBE_CONTEXT" -n "$NAMESPACE" --wait --timeout "$HELM_TIMEOUT"
    echo "Functional check failed; restored revision $prior." >&2
  else
    helm uninstall "$RELEASE" --kube-context "$KUBE_CONTEXT" -n "$NAMESPACE" --wait
    echo 'Initial release failed functional check; removed release.' >&2
  fi
  exit 1
fi
