# GPU platform incident runbook

Always pass an explicit kube context and collect timestamps, events, image digest, AMI ID, Kubernetes version and driver version. Never include API keys or user prompts in an incident record. Commands below are read-only unless stated otherwise.

## Pending pod

Inspect `kubectl --context "$KUBE_CONTEXT" -n modelops describe pod POD`, NodeClaims, NodePool status and Karpenter logs. Separate admission rejection (quota), scheduling failure (GPU request/taints/selectors), provisioning failure (EC2 quota, capacity or IAM), volume failure (EBS attachment/AZ), and startup failure (model download or vLLM).

- No NodeClaim: check pod GPU request, pool requirements and one-GPU limit; controllers must run on the CPU system pool.
- NodeClaim cannot launch: inspect IAM, region instance offerings, EC2 GPU quota and interruption queue configuration. Switching capacity type or instance families is a reviewed change, not an automatic retry loop.
- Node exists but has no allocatable GPU: check NFD labels, device-plugin pods, NVIDIA driver and toolkit on the pinned AMI. Do not enable a second driver installer on top of the AMI to hide the fault.
- PVC Pending: inspect StorageClass, EBS CSI Pod Identity and AZ constraints. An existing ReadWriteOnce cache pins subsequent scheduling to its volume's AZ. Do not delete a volume before deciding whether its data is disposable.

## Memory pressure

`GPUMemoryPressure` means framebuffer allocation stays above 95%, not proof of an OOM. vLLM reserves GPU memory for cache; sustained allocation can be intentional. Correlate memory with completion failures, pending requests and process logs. Check max model length, model precision and concurrency. Change one setting at a time, record image/model settings, then measure throughput and tail latency on real hardware. Reduce workload pressure or revert the last release before increasing cost. The current gateway's bound is per replica, not global.

## Hardware error

`GPUHardwareError` surfaces a nonzero NVIDIA XID field. Interpret the specific code using NVIDIA documentation and collect `nvidia-smi` output and driver/kernel logs. A persistent last-error code may remain visible after the original event; do not automatically recycle nodes for every alert.

If evidence points to a device/driver failure, plan interruption, set the model replicas to zero through GitOps, and isolate the affected node. Cordon/drain or replacement is a mutating operator action; ensure no valuable workload or volume attachment is abandoned. With one model replica, replacement causes downtime. Preserve evidence before replacing the node. After recovery, verify the device, DCGM, and a real completion; close the incident with the observed cause and recovery time.

## Missing telemetry

`GPUTelemetryMissing` fires only when Kubernetes advertises at least one GPU and no DCGM utilization series exists cluster-wide for ten minutes. It does not detect one missing exporter in a larger otherwise-healthy fleet. Inspect exporter DaemonSets, taint tolerations, ServiceMonitor selection, scrape targets and operator health. Empty dashboards on a CPU-only cluster are expected, not a simulated success.

## Capacity and cost

Check allocatable GPU resources against requested GPU resources and NodeClaims. A low-utilization GPU with a running model remains allocated; Karpenter does not infer a decision to stop serving. Scale the backend to zero through the reviewed workload Application, verify node termination, and record cold-start time before bringing it back. Do not treat budgets or NodePool limits as a guaranteed financial cutoff.

## Failed release

Inspect readiness and startup events before restarting repeatedly. The startup allowance covers model loading; liveness only takes over after startup succeeds. If acceptance fails, restore the previous chart commit and image digest in Git, advance the root revision, and manually sync the workload. Preserve failed-release events. Changes to model/storage formats may require an explicit compatibility decision rather than a blind rollback.
