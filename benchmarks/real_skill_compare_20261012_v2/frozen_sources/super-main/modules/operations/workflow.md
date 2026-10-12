# Reliability, Observability and Performance

## Targets and implementation

Define SLOs from expected users and critical journeys: availability, latency percentiles, error
rate and expected traffic. Do not invent universal latency or uptime thresholds.
Instrument bounded-cardinality metrics, structured logs, correlation IDs and traces where useful.
Use [OpenTelemetry](https://opentelemetry.io/docs/what-is-opentelemetry/) with the project's existing
backend; a telemetry library does not provide dashboards/alerts by itself.
Separate process liveness from dependency readiness; make startup/shutdown and timeouts predictable.
Redact sensitive data, and verify alert routing and diagnostic information on controlled failures.

## Resilience and load scenarios

Configure `operations.resilience` for relevant DB/upstream timeout, failed job, readiness transition
and recovery scenarios. Assert controlled responses, retained data and restored functionality.
Do not introduce retries/circuit breakers without testing their effects on load and duplicate writes.
Coordinate restoration with [data](../data/workflow.md); own the incident/recovery runbook.

Configure `operations.load` with representative data and a dedicated target, using
[k6](https://grafana.com/docs/k6/latest/using-k6/thresholds/) or the project's load runner.
Declare thresholds, traffic shape, concurrency, duration and cold/warm-cache assumptions.
The adapter requires actual iterations and every named threshold; zero activity cannot pass.
Measure slow queries, event-loop/CPU/memory bottlenecks and cost before optimizing.
Report only measured workloads and environments; passing one load test is not global capacity proof.

Use [Google SRE SLO guidance](https://sre.google/workbook/implementing-slos/) to choose meaningful
signals and incident actions. In release mode, missing resilience/load evidence remains a blocker.
