# Deploying to an existing cluster

The default supported demonstration is `make kind`. For staging, first choose and provision an appropriate cluster; this repository does not silently create billable infrastructure.

1. Create namespace `modelops` and a Secret named `modelops-api-key` containing key `api-key`. Use a secret manager or a generated manifest over stdin. Never place credentials in values files or Helm command-line values.
2. Select a successful commit-tagged GHCR image. If the package is private, configure the namespace's image pull access or make the package public through GitHub package settings.
3. Set `KUBE_CONTEXT`, `API_KEY` (the same value as the Secret), `IMAGE_REPOSITORY=ghcr.io/pranaysparihar/model-ops`, and `IMAGE_TAG=<full verified commit SHA>`.
4. For CPU simulation, run `scripts/deploy.sh`.
5. For GPU inference, also set `VALUES_FILE=deploy/environments/gpu.yaml`, `MODEL=Qwen/Qwen2.5-0.5B-Instruct`, and `HELM_TIMEOUT=20m`. The gateway and backend model alias must match.

The GPU profile requires NVIDIA drivers/device plugin, a node labeled `nvidia.com/gpu.present=true`, a default storage class for the model cache, adequate memory, and outbound model download access. Adjust placement and resources for actual hardware. The GPU profile is not yet hardware-tested.

## Cloud delivery

The AWS platform uses [Argo CD promotion](cloud-platform.md), replacing the earlier workflow that stored a staging kubeconfig. `Prepare GitOps promotion` now verifies a successful CI run and produces the chart SHA/image digest pair for a reviewed environment commit; it never receives cluster credentials or deploys directly.

Use the standalone Helm procedure above only for clusters/releases not managed by Argo. Internet exposure remains outside this private lab; TLS ingress, end-user identity and egress restrictions need an explicit design.
