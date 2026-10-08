# Validation record

Validated on 2026-10-08 using a macOS ARM64 host, Docker Desktop, kind Kubernetes, and Helm 4. GitHub CI separately targets Linux amd64, Python 3.12, and Helm 3. Consult the workflow badge and artifacts for that run's result.

## Executed locally

- 13 gateway tests passed: authentication, validation, body limits, backend errors, malformed responses, metrics/log handling, concurrency rejection, and timeout capacity recovery.
- Native HTTP integration passed: real Uvicorn processes, authenticated completion, readiness loss during a dependency failure, and recovery without restarting the gateway.
- Docker image built and ran as UID 10001 with read-only root filesystem.
- Helm installation into `kind-modelops-lab` passed authenticated functional verification.
- A deliberately nonexistent image caused a failed rollout and automatic restoration of the prior image.
- A release that passed readiness but failed authenticated smoke verification triggered explicit rollback to the previously deployed revision.
- Backend pod deletion produced a different pod UID and a successful authenticated completion after recovery.
- Compose Prometheus target reported `up`; Grafana health reported its database `ok`.
- Promtool accepted the configuration and alert rules. Helm lint, rendered manifest assertions, Ruff, and actionlint passed.
- Trivy 0.74.0 reported no **fixable high/critical** findings in the built gateway image at test time. This scoped result is not a guarantee that the image has no vulnerabilities.

## Load samples

Raw results: [baseline](evidence/baseline-simulator.json), [overload](evidence/overload-simulator.json). The backend is a fixed 150ms CPU simulator, not a language model. The driver is closed-loop, with no retry/backoff or arrival-rate control. The high-concurrency sample aggressively sends new work when a request is rejected; it demonstrates admission control, not sustainable throughput. Full completion latency is reported only for successful responses, alongside all HTTP status counts.

[Native checks](evidence/native-check.json) and [Kubernetes drill log](evidence/drill.log) preserve the local evidence. CI generates fresh evidence on each run rather than relying on these samples.

## Not verified or claimed

Actual GPU inference, model accuracy, NVIDIA scheduling, hardware-dependent vLLM startup, enforced NetworkPolicy on kind's default CNI, cloud costs, externally routed alert notifications, continuous uptime, and production traffic. No SLO attainment or customer adoption is claimed.
