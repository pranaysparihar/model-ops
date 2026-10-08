# Architecture decisions

## The user and the intent

A small team has a model endpoint, but releasing changes requires shell commands and tribal knowledge. An operator needs a reproducible release, a signal when user requests fail, and a tested recovery path. ModelOps makes those three paths inspectable. It is a portfolio reference implementation, not a customer-validated commercial platform.

## Why a simulator ships alongside vLLM

A GPU requirement makes delivery checks expensive and difficult for contributors. The deterministic backend exercises HTTP contracts, probes, scheduling, rollout, and reconciliation on CPUs. It deliberately makes no claims about model quality, GPU behavior, or actual inference performance. The GPU profile uses the same gateway contract but requires a separate hardware acceptance test.

## Small failure boundaries

Liveness checks the gateway process; readiness checks its dependency. A dependency outage makes the gateway unready instead of causing restart loops. There are no automatic inference retries: a retry can duplicate expensive work and amplify overload. Excess valid requests receive 429 and a Retry-After hint. Callers should use capped exponential backoff with jitter.

The gateway forwards only the fields this version supports. Unknown model names, streaming, oversized inputs, and excessive output-token requests are rejected. Deadlines cover the whole outbound request. Cancellation releases the in-flight slot even when the dependency fails. Metrics use fixed outcome labels rather than prompts, identities, model strings, or raw paths.

## Release safety

The independent local lab uses Helm rollback as described below. The AWS platform uses reviewed Argo CD promotion with a pinned chart revision and image digest; see [cloud delivery](cloud-platform.md). Its functional rollback is an operator-reviewed Git revert and sync, not the local Helm rollback script.

Helm waits for probes and automatically rolls back failed upgrades. Probe success alone is insufficient, so the release script also makes an authenticated completion request. If this fails, it rolls back to the prior deployed revision (or removes a failed first installation). This is rolling delivery with rollback, not a canary rollout.

The backend uses Recreate because the default GPU budget is one device and a single ReadWriteOnce cache. This implies downtime during model changes. Two GPUs, warm replicas, and traffic shifting are required to investigate zero-downtime backend rollouts.

## Cost and capacity

Defaults cap gateway CPU/memory, completion size, and in-flight requests. The standalone GPU profile requests exactly one GPU. The AWS composition also supplies a Karpenter NodePool that can provision matching GPU nodes; this path still requires cloud validation. There is no claimed cost reduction. Record the provider's actual hourly price, elapsed runtime, idle time, and successful request count before calculating cost per request. A price spreadsheet without workload and idle assumptions is misleading.

Request-driven replica autoscaling comes after measuring model loading time and sustainable concurrency. Karpenter node provisioning and empty-node consolidation are already configured separately. CPU usage at the gateway is not an appropriate signal for GPU inference capacity. Start with queue/in-flight pressure, model memory constraints, and a tested capacity target.

## Next steps justified by evidence

1. Validate the GPU profile on chosen hardware and publish measurements.
2. Exercise network policy and ingress TLS in a representative cluster.
3. Add notification routing and persistent monitoring storage for continuous operation.
4. Introduce a second backend only when availability requirements justify the cost.
5. Validate EKS Pod Identity, GitOps bootstrap and manual workload rollback in the actual AWS environment. Stored staging kubeconfigs have been removed from the cloud delivery workflow.
