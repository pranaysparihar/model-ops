# Security scope

This is a private-network reference lab, not a hardened multi-tenant hosting service. Report vulnerabilities through GitHub private vulnerability reporting if enabled; do not post credentials or sensitive logs in issues.

Inference requires a shared API key. Metrics and health endpoints are intended for trusted network access. Keep Compose on localhost and Kubernetes services private. The simulator is only a test backend. There are no real credentials in repository defaults.

Container and dependency versions are pinned where practical; the Python base tag tracks security patches. Rebuilds can therefore produce a new base digest. Published CI images carry a commit tag, provenance, and SBOM. Review dependencies and image findings before internet deployment.
