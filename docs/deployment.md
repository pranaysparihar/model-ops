# Deploying to an existing cluster

The default supported demonstration is `make kind`. For staging, first choose and provision an appropriate cluster; this repository does not silently create billable infrastructure.

1. Create namespace `modelops` and a Secret named `modelops-api-key` containing key `api-key`. Use a secret manager or a generated manifest over stdin. Never place credentials in values files or Helm command-line values.
2. Select a successful commit-tagged GHCR image. If the package is private, configure the namespace's image pull access or make the package public through GitHub package settings.
3. Set `KUBE_CONTEXT`, `API_KEY` (the same value as the Secret), `IMAGE_REPOSITORY=ghcr.io/pranaysparihar/model-ops`, and `IMAGE_TAG=<full verified commit SHA>`.
4. For CPU simulation, run `scripts/deploy.sh`.
5. For GPU inference, also set `VALUES_FILE=deploy/environments/gpu.yaml`, `MODEL=Qwen/Qwen2.5-0.5B-Instruct`, and `HELM_TIMEOUT=20m`. The gateway and backend model alias must match.

The GPU profile requires NVIDIA drivers/device plugin, a node labeled `nvidia.com/gpu.present=true`, a default storage class for the model cache, adequate memory, and outbound model download access. Adjust placement and resources for actual hardware. The GPU profile is not yet hardware-tested.

## GitHub deployment environment

The manually triggered `Deploy verified image` workflow targets an environment named `staging`. Configure required reviewers in GitHub and these environment secrets:

- `KUBECONFIG_B64`: base64-encoded, namespace-scoped staging kubeconfig with only the permissions needed for Helm-managed resources and port-forwarding.
- `MODELOPS_API_KEY`: the existing API secret value, used only for functional verification.

The runner must reach the Kubernetes API. Private clusters need an appropriately networked runner. The workflow checks that the requested full SHA has a successful main-branch CI run before deploying. Credentials are written with restrictive permissions and removed on exit. No long-lived cluster credentials are included in this repo.

The initial implementation uses an environment kubeconfig for provider neutrality. Prefer cloud workload identity/OIDC when integrating a chosen cloud. Internet exposure is out of scope for this private lab; TLS ingress, path-level access, quotas, and tenant isolation need their own review.
