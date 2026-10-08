# Reliability objectives

These are design targets, not achieved production SLAs.

## Availability

Target: 99.9% of valid, authenticated completion attempts succeed over a rolling 30-day window. The eligible outcomes are success, upstream_error, timeout, and overloaded. **429 is a failed user experience and consumes the budget.** Authentication and validation failures are excluded.

SLI = successful attempts / eligible attempts. An empty window is insufficient data, not 100% availability. Request count matters: for N eligible attempts, allowed failures = 0.001 × N. Downtime in minutes is not interchangeable with this request-based budget.

The fast-burn rule evaluates a 5-minute error fraction over 1.44% (14.4 times the 0.1% budget), with at least 20 eligible requests and a 2-minute hold. This is a lab alert, not a complete multi-window paging policy. Tune traffic floors for the service and add a long-window condition before production paging.

## Latency

Simulator reference objective: 95% of successful, short non-streaming completions finish within 5 seconds. `modelops_request_duration_seconds` measures full response time, not time to first token. Prometheus histogram aggregation preserves cross-replica quantiles. GPU model objectives must be chosen from the actual workload rather than inherited from this simulator.

## Missing traffic and missing telemetry

Prometheus scrape failure is separate from completion failure. Scrapes cannot prove that an endpoint remains externally reachable or that credentials work. CI smoke tests cover the API contract during releases; continuous operation needs an external authenticated synthetic check. No traffic yields no inference success claim.

## Error budget policy

If the measured 30-day budget is exhausted, pause feature releases and prioritize recovery fixes. Security fixes remain eligible. The repository documents this operating policy; automated release freezing is not implemented.
