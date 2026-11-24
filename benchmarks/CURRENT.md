# Controlled benchmark matrix — 24 November 2026

This experiment measures Redis, PgBouncer and replica-count changes on the current application under a fixed offered load. It supplements the [historical record](PROGRESS.md); it does not reconstruct missing November 19 hardware or single-instance results.

## Environment and provenance

- Windows host: Intel Core i5-12450HX, 8 physical cores / 12 logical processors, 24 GiB installed RAM (25,769,803,776 bytes from DIMM capacities); Windows reports 23.71 GiB of physical memory (25,463,480,320 bytes). See the [host-memory capture](results/2026-11-24-matrix/host-memory.json).
- Docker Desktop: 12 logical CPUs, 12,389,138,432 bytes of engine-visible memory (11.54 GiB), Engine 29.5.3, Compose v5.1.4, WSL2 kernel 6.6.87.2.
- k6 v2.2.0, limited to 8 CPUs and 8 GiB per generator container. The generator and all stack services share the same physical host and Docker VM. These limits do not reserve dedicated resources.
- [Runtime versions](results/2026-11-24-matrix/runtime-versions.json): Node.js 22.23.5, PostgreSQL 16.15, Redis 7.4.11, PgBouncer 1.26.1 and NGINX 1.27.5.
- Tested application/workload revision: `721dfeccf9b70e294dad48e94912a1688d67ebe7`. The [environment capture](results/2026-11-24-matrix/environment.json) records exact image identities and source SHA-256 hashes. Later report/visual changes do not alter the tested application.
- All HTTP traffic takes the same internal path: k6 container → NGINX → Fastify. No host-published port is used.

## Method

Five configurations are tested twice, sequentially. Pass one follows the order below; pass two reverses it. This reduces a simple order bias but does not eliminate shared-host noise or substitute for many repetitions.

| Configuration       | API replicas | Redis               | Database route    |
| ------------------- | -----------: | ------------------- | ----------------- |
| `1-direct-no-cache` |            1 | Disabled explicitly | Direct PostgreSQL |
| `1-direct-redis`    |            1 | Enabled             | Direct PostgreSQL |
| `1-pool-redis`      |            1 | Enabled             | PgBouncer         |
| `3-pool-redis`      |            3 | Enabled             | PgBouncer         |
| `8-pool-redis`      |            8 | Enabled             | PgBouncer         |

Before every run the isolated database is truncated and reseeded to 100,000 articles, Redis is flushed, and API/cache state is checked. PostgreSQL buffer and host filesystem caches are not deliberately evicted. The API image, NGINX configuration and database pool settings remain fixed. Redis and PgBouncer services remain running even when bypassed so topology changes are limited to the intended routing switch.

Each run lasts four minutes: 30 seconds ramping to 250 iterations/s, one minute ramping to 1,000, two minutes at 1,000, then 30 seconds ramping to zero. All RPS and latency statistics cover the entire run, including ramps. A successful run averages approximately 742 HTTP requests/s over this schedule; that is not the plateau rate or maximum capacity.

The mix is 80% single-article reads, 15% list reads and 5% writes. Deletes first create a target, so approximately 1% of iterations issue two HTTP requests. A fixed seed stabilizes each VU's random choices, but changing VU scheduling can change the aggregate trace. Reads use the existing synthetic skewed distribution, not real user traffic. Every run uses 300 preallocated and 1,000 maximum VUs.

Acceptance requires zero dropped iterations, HTTP failure rate below 1%, p95 below 250 ms and p99 below 500 ms. A failed run stays in the table and the raw evidence. A run with zero HTTP failures can still fail because it did not schedule all offered iterations.

## Results and artifacts

Seven of ten runs passed all thresholds. Both no-cache runs had higher p95 than either direct-database Redis run (50.71–70.42 ms versus 12.34–37.92 ms), but Redis alone still dropped 458 and 7 iterations. The no-cache baseline passed once and failed once; its first run had 1,117 failed HTTP requests and 2,091 drops. This variability is part of the result.

Adding PgBouncer to the one-replica Redis configuration passed both repetitions, with zero HTTP failures or drops. Its p95 ranged from 5.11 to 13.63 ms. Three replicas passed both with a narrower observed p95 range of 5.20–5.94 ms; eight also passed both but had higher p95 (11.85–13.71 ms) and p99 (51.63–56.75 ms) than three. At this offered load there is no demonstrated throughput advantage from eight replicas. These are observations from two runs, not general speedup guarantees or an explanation of the underlying bottleneck.

The [compact comparison](results/2026-11-24-matrix/compact.md) reports ranges across repetitions and sums absolute counts. The README uses the same values.

The [per-run results table](results/2026-11-24-matrix/comparison.md) links to every retained k6 log. [Machine-readable comparison data](results/2026-11-24-matrix/comparison.json) is derived from the original JSON summaries by `benchmarks/summarize.py`; it validates absolute failure counts and exit status against the thresholds. Summary percentiles are not pooled across runs. Compact tables and visuals show the observed range of the two repetitions, not confidence intervals.

Each run directory contains:

- `k6.log`: complete captured output, including failed thresholds.
- `summary.json`: original k6 metrics including p99, request counts, cache counters and drops.
- `run.json`: configuration, exact command, timestamps, initial/final row counts, replica health and exit status.
- `resources.jsonl`: timestamped Docker stats, PostgreSQL connections and PgBouncer pool samples.

`environment.json` records the start/end of the matrix, source provenance and machine information. Resource observations occur roughly every 15 seconds plus command execution time. Sampled PostgreSQL session counts in the comparison data exclude the monitoring query's own connection; they are observations, not continuous maxima or measurements of productive query work.

### Ten-minute confirmation attempts (excluded)

Two 10-minute-plateau runs of `3-pool-redis` were attempted after the matrix, each with a fresh 100,000-row dataset. Both are retained — [first attempt](results/2026-11-24-soak) and [repeat](results/2026-11-24-soak-r2) — but neither is used in the README, comparison tables or visuals: the host stalled during both.

| Attempt | Wall clock for a 12-minute schedule | Max `http_req_duration` | Whole-run HTTP RPS | Resource-sampling gap |
| ------- | ----------------------------------: | ----------------------: | -----------------: | --------------------: |
| First   |                          98 minutes |                 1h26m5s |             112.67 |            5,198.75 s |
| Repeat  |                              16m15s |                   4m11s |             681.10 |              273.58 s |

Both k6 runs exited 0 with zero failed requests, zero drops and passing printed thresholds (first: p95 23.96 ms, p99 89.2 ms; repeat: p95 4.37 ms, p99 9.46 ms). The stalls distort whole-run throughput and add extreme latency outliers, so none of these values is presented as a clean sustained-load measurement. The 32 and 39 resource samples — roughly 390 were expected at the intended 15-second cadence — and the matching gaps corroborate the stalls.

No clean 10-minute confirmation run exists in this matrix; the historical ten-minute result in [PROGRESS.md](PROGRESS.md) remains a separate historical record.

## Interpretation limits

- These are fixed-load acceptance/latency comparisons, not a search for each configuration's maximum sustainable throughput. Similar RPS is expected when configurations can both serve the same offered workload.
- Two repetitions reveal variation but are insufficient for a precise general speedup estimate. Changing replica count also changes the aggregate API connection-pool allowance (ten per replica), as it does in the application configuration.
- The host remains a shared Windows/Docker Desktop development machine. Other applications and the resource sampler can compete with k6 and the stack. There is no native Linux or dedicated-generator control.
- Some raw duration samples are negative in Docker/WSL. The original summaries are retained unchanged; reported tail percentiles are descriptive observations under this timing limitation, not precision latency guarantees.
- Cache-hit rates apply only to responses counted with `X-Cache: HIT` or `MISS`, not list/write requests or the no-cache configuration.
- These tests do not establish production readiness, cache consistency during races, Redis failover, authorization, or high availability. Those remain documented engineering work.

Reproduce the experiment using the [isolated matrix runbook](RUNBOOK.md#controlled-comparison-matrix).
