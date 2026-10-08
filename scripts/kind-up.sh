#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export KUBE_CONTEXT=kind-modelops-lab
if ! kind get clusters | grep -qx modelops-lab; then
  kind create cluster --name modelops-lab --config deploy/kind.yaml
fi
docker build -t modelops:local .
kind load docker-image modelops:local --name modelops-lab
kubectl --context "$KUBE_CONTEXT" create namespace modelops --dry-run=client -o yaml | kubectl --context "$KUBE_CONTEXT" apply -f -
./scripts/init-env.sh
set -a
source .env
set +a
# Pipe a generated manifest; key does not appear in command arguments or saved YAML.
python3 - <<'PY' | kubectl --context "$KUBE_CONTEXT" -n modelops apply -f -
import json, os
print(json.dumps({'apiVersion':'v1','kind':'Secret','metadata':{'name':'modelops-api-key'},'stringData':{'api-key':os.environ['API_KEY']}}))
PY
IMAGE_TAG=local ./scripts/deploy.sh
