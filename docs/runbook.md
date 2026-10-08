# Operational runbook

## A release fails

1. Read CI artifacts and `helm history modelops -n modelops --kube-context <context>`.
2. Check pod events (`kubectl describe pod`) for missing image, missing secret, scheduling, or probe failures.
3. `scripts/deploy.sh` should already have restored the prior revision after an upgrade/readiness or functional failure. Verify the deployment's image, rollout status, and an authenticated completion.
4. If manual rollback is necessary, select the known-good revision from history, then `helm rollback modelops <revision> -n modelops --kube-context <context> --wait`.
5. Rollback does not undo persistent data changes. This gateway has no mutable application database. Future schema changes need their own migration policy.

## Availability alert

- Split metrics by outcome. Overloaded: inspect in-flight load and caller retry behavior. Timeout: inspect backend latency and GPU pressure. Upstream error: inspect backend logs, health, model load, and memory.
- Check `/health/live` and `/health/ready` separately. A live gateway with a failed readiness check points to the dependency.
- Use `X-Request-ID` to correlate gateway logs. Logs intentionally exclude prompts and API keys.
- Reduce offered load before increasing concurrency. Raising concurrency can increase memory pressure and make the incident worse.
- Record a UTC timeline, impact, contributing conditions, recovery action, and follow-up test. Do not claim recovery until an authenticated completion works.

## Disposable lab drills

`make drill` restricts all mutations to `kind-modelops-lab`. It deliberately deploys a nonexistent image, checks rollback, checks that a failed functional verification also rolls back, deletes a backend pod, checks replacement, and verifies completion. It exits nonzero on failed assertions and writes `artifacts/drill.log`.

For an HTTP failure in Compose:

```sh
docker compose exec simulator touch /tmp/modelops-fail
# readiness returns 503; completion requests return 502
make smoke  # expected to fail
# restore the simulator
docker compose exec simulator rm /tmp/modelops-fail
make smoke  # expected to pass
```

There is no network-accessible fault administration endpoint. Do not run these exercises against a production service.

## Teardown

`make down` removes Compose containers. `make clean-lab` deletes the named kind cluster and its ephemeral monitoring data. Neither command touches a cloud cluster. GPU cloud resources, if separately provisioned, must be removed through their owner's infrastructure workflow.
