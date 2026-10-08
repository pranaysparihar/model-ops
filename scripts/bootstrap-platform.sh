#!/usr/bin/env bash
# Installs controllers into an EXISTING cluster. Never provisions AWS infrastructure.
set -euo pipefail
cd "$(dirname "$0")/.."
: "${KUBE_CONTEXT:?Set an explicit KUBE_CONTEXT}"
: "${PLATFORM_VALUES:?Set a committed path relative to platform, e.g. environments/aws.yaml}"
: "${PLATFORM_REVISION:?Set the reviewed Git commit containing PLATFORM_VALUES}"
[[ "$PLATFORM_REVISION" =~ ^[0-9a-f]{40}$ ]] || { echo 'Use a full commit SHA'; exit 1; }
[[ "$PLATFORM_VALUES" == environments/*.yaml && "$PLATFORM_VALUES" != *..* ]] || exit 1
helm template platform platform -f "platform/$PLATFORM_VALUES" >/dev/null
k=(kubectl --context "$KUBE_CONTEXT")
for ns in argocd monitoring; do
  "${k[@]}" create namespace "$ns" --dry-run=client -o yaml | "${k[@]}" apply -f -
done
if ! "${k[@]}" -n monitoring get secret grafana-admin >/dev/null 2>&1; then
  python3 - <<'PY' | "${k[@]}" apply -f -
import json, secrets
print(json.dumps({'apiVersion':'v1','kind':'Secret','metadata':{'name':'grafana-admin','namespace':'monitoring'},'stringData':{'admin-user':'admin','admin-password':secrets.token_urlsafe(32)}}))
PY
fi
helm upgrade --install argocd argo-cd --repo https://argoproj.github.io/argo-helm \
  --version 10.10.1 --namespace argocd --kube-context "$KUBE_CONTEXT" \
  -f platform/bootstrap/argocd.yaml --wait --timeout 10m
# ModelOps is public, so Argo can fetch it without a Git credential.
# Private repositories need a read-only Argo repository Secret configured separately.
export PLATFORM_VALUES PLATFORM_REVISION
python3 - <<'PY' | "${k[@]}" apply -f -
import json, os
print(json.dumps({
 'apiVersion':'argoproj.io/v1alpha1','kind':'Application',
 'metadata':{'name':'modelops-platform','namespace':'argocd'},
 'spec':{'project':'default','source':{'repoURL':'https://github.com/pranaysparihar/model-ops.git','targetRevision':os.environ['PLATFORM_REVISION'],'path':'platform','helm':{'valueFiles':[os.environ['PLATFORM_VALUES']]}},'destination':{'server':'https://kubernetes.default.svc','namespace':'argocd'},'syncPolicy':{'automated':{'prune':True,'selfHeal':True},'syncOptions':['ServerSideApply=true']}}}))
PY
echo 'Root application installed. Check child sync/health before promoting a workload.'
