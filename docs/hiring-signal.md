# Why build this platform?

The intended user is a small engineering team that needs a shared, privately hosted model endpoint without hand-configuring GPU machines for every release. The platform operator must make capacity, access, releases, and recovery repeatable. Model serving is the workload; infrastructure is the project.

Success means an operator can explain **who may deploy, how a pending GPU pod gets capacity, how secrets arrive without static AWS keys, what costs persist while inference is idle, and how a failed release is reversed**. A dashboard alone cannot demonstrate those abilities.

## Hiring research, 8 October 2026

This is a small sample of relevant job descriptions, not a census of DevOps jobs. Some are senior roles; building this lab does not establish equivalent professional experience. GPU fleet expertise is a specialization rather than a universal DevOps prerequisite.

| Requirement seen in postings | Evidence in this repository | Boundary |
|---|---|---|
| AWS, EKS, Terraform; networking and IAM | `infra/aws`: two-AZ VPC, private workers, allowlisted operator API option, access entries, Pod Identity, flow logs | Validated configuration and mocked plans; no AWS deployment claimed |
| Kubernetes/GitOps delivery | Restricted Argo workload project, controller applications, digest-pinned workload promotion | Rendered contracts; cloud Argo bootstrap still requires acceptance |
| GPU scheduling and autoscaling | Karpenter NodePool/EC2NodeClass, exact NVIDIA AMI, taints/tolerations, GPU Operator integration | Real scheduling, drivers and scale-down require hardware |
| Observability, incidents and SLOs | DCGM alerts with rule tests, GPU dashboard, pending-pod and hardware runbooks; existing rollback drills | Local recovery evidence; no production uptime claim |
| Security and resource isolation | Namespace quota, restricted Pod Security, scoped secret IAM, default-deny ingress | Cilium enforcement tested locally; AWS VPC CNI must be retested |
| Cost awareness | Small GPU instance allowlist, one-GPU target, empty-node consolidation, budget alert, explicit idle-cost discussion | Budgets notify; Karpenter limits are eventually consistent and not billing caps |

Sources:
- [Level — Senior Infrastructure Engineer](https://jobs.ashbyhq.com/level/c6897f8f-f8f4-4df1-897a-a3c2c021de6d): AWS, EKS, Terraform/OpenTofu, Karpenter, Argo CD, IAM and observability.
- [TypeSafe — Infrastructure / Developer Platform](https://jobs.ashbyhq.com/typesafe-ai/acea2aac-d1d4-4d18-8839-7c6051371c43): cloud, Kubernetes, GPU infrastructure, autoscaling and SLOs.
- [fal — Infrastructure Engineer](https://jobs.ashbyhq.com/fal-ai/b8c5f81c-89c4-45c7-a1d9-3c190a523268): GPU fleet operations, Linux, drivers/runtimes and infrastructure automation.
- [Alchemy — Infrastructure](https://jobs.ashbyhq.com/alchemy/42c849ce-8a9b-4015-92fb-b8dfad5c5d0d): Terraform, GitOps, reliability, IAM and cost.
- [Material — Infrastructure](https://jobs.ashbyhq.com/material/dc0ab16b-4df2-4c0b-abc3-f436d97fd96f/): GPU infrastructure, scheduling and capacity controls.

## Decisions worth discussing in an interview

1. **Buy the inference engine, build the operating path.** vLLM does inference. This repository demonstrates infrastructure ownership rather than reimplementing a model server.
2. **Separate CPU controllers from GPU capacity.** Argo, Karpenter and monitoring remain available when the GPU pool is empty. GPU pods carry explicit resource requests and tolerate only their dedicated pool's taint.
3. **One driver owner.** EKS AL2023 NVIDIA AMIs supply the driver and toolkit. GPU Operator supplies discovery, device-plugin and telemetry components with driver/toolkit installation disabled. Two owners would create upgrade and compatibility risk.
4. **Limit blast radius before adding scale.** One model replica, one-GPU quota, small instance allowlist, private services and manual workload promotion. This trades availability for an affordable, understandable lab.
5. **Test failures, not just configuration syntax.** An untrusted namespace must time out while monitoring succeeds; a second GPU reservation must be rejected; a privileged workload must fail admission. A YAML file alone is insufficient evidence.
6. **Separate node scaling from request scaling.** Karpenter supplies nodes for unschedulable pods. This project deliberately does not claim traffic-based inference autoscaling. A running idle model still occupies its GPU until its replica count is reduced.
7. **Be precise about evidence.** A local policy test proves those policies on Cilium. It does not prove AWS VPC CNI behavior, CUDA compatibility, cloud IAM, inference throughput or cost savings.

## Suggested demonstration

Show the architecture and cost decisions first, then the successful CI and local network/admission report. Explain a GPU Pending incident using the runbook, show the exact release digest and Argo project boundary, then demonstrate existing failed-release rollback. Only show GPU utilization or benchmark results after running the hardware acceptance procedure on a real GPU.
