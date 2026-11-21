# Benchmark results — 19 November 2026

This is the historical experiment record. Raw logs are retained unchanged, including failed and incomplete runs. Workload arrival rate and HTTP throughput are different units.

## Accepted long runs

Both runs configured a ten-minute plateau at 1,000 iterations/second, with 90 seconds of ramp-up and 30 seconds of cooldown. Percentiles cover the entire run. Each iteration makes one request except the create-then-delete branch, which makes two when creation succeeds.

| Path                                                                                         | Configuration recorded at the time                 | HTTP requests | Aggregate requests/s |      p95 |      p99 | Failed requests | Dropped iterations |
| -------------------------------------------------------------------------------------------- | -------------------------------------------------- | ------------: | -------------------: | -------: | -------: | --------------: | -----------------: |
| [Compose network](stress-internal-10m.log)                                                   | 3 replicas, before PgBouncer                       |       662,890 |               920.78 |  7.78 ms | 27.16 ms |               0 |                  0 |
| [Published port from a Linux bridge inside Docker Desktop](stress-published-linuxvm-10m.log) | 8 replicas, with PgBouncer, ETags, fill coalescing |       663,132 |               921.10 | 11.70 ms | 27.95 ms |               0 |                  0 |

The second run completed 656,399 iterations, with 522,009 cache hits and 2,848 misses reported through `X-Cache`. It used at most 36 active VUs out of 300 preallocated. Aggregate throughput includes ramps. At a 1,000-iteration plateau, the workload generates approximately 1,010 HTTP requests/second because about 1% of iterations perform two requests.

These runs changed both configuration and network path. They do not isolate replica scaling or PgBouncer's effect, and neither finds maximum sustainable throughput.

## Other retained evidence

| Log                                                                                                                                      | Interpretation                                                                             |
| ---------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| [smoke-internal.log](smoke-internal.log)                                                                                                 | 30-iteration/s smoke test; thresholds passed                                               |
| [stress-internal-2m.log](stress-internal-2m.log)                                                                                         | Short Compose-network acceptance run                                                       |
| [stress-8replicas-2m.log](stress-8replicas-2m.log)                                                                                       | Eight-replica short run; p95 5.56 ms, p99 9.48 ms                                          |
| [stress-published-linuxvm-2m.log](stress-published-linuxvm-2m.log)                                                                       | Short published-port run within Docker VM                                                  |
| [replica-failure-under-load.log](replica-failure-under-load.log)                                                                         | One failed HTTP request out of 178,159; zero dropped iterations; p95 5.54 ms, p99 18.70 ms |
| [stress-host-2m.log](stress-host-2m.log)                                                                                                 | Host-path experiment; not evidence for the accepted long run                               |
| [stress-host-loopback-2m.log](stress-host-loopback-2m.log), [stress-host-noproxy-2m.log](stress-host-noproxy-2m.log)                     | Short host-loopback experiments                                                            |
| [stress-host-loopback-10m.log](stress-host-loopback-10m.log), [stress-host-noproxy-10m.log](stress-host-noproxy-10m.log)                 | Long host-path runs failed the zero-drop requirement; 282–287 dropped iterations           |
| [stress-final-3replicas-10m.log](stress-final-3replicas-10m.log), [stress-host-noproxy-500vu-10m.log](stress-host-noproxy-500vu-10m.log) | Incomplete after session timeouts; excluded from acceptance                                |

The failure experiment's printed `0.00%` is rounded: it had one failed request. It met the configured error budget during that stop, but did not demonstrate lossless failover. Some logs contain negative minimum request durations; timing anomalies are retained rather than silently corrected.

## Environment and missing provenance

Experiment notes record Windows with Docker Desktop, Docker Engine 29.5.3, and 229,346 articles after earlier writes. The original seed contains 100,000 articles. Stress runs used the `realistic` access pattern, an initially empty Redis cache, 300 preallocated VUs, a 1,000-VU maximum, and k6 container limits of 8 CPUs and 8 GB.

Those limits do not establish dedicated hardware or generator headroom. CPU model, host memory, Docker VM allocation, image digests, source revisions, and plateau-only time series are absent. Network-path differences are an observed association; summaries alone do not prove the cause of dropped iterations. No native Linux host was tested.

Earlier notes report 8 PgBouncer client connections and 5 server connections during a pool inspection, but no machine-readable snapshot was retained. These are not established sustained-load measurements.

## Unmeasured questions

- Maximum sustainable rate, with repeated runs and uncertainty estimates.
- Replica scaling with fixed hardware, network, dataset, and code.
- Uniform versus skewed reads under identical conditions.
- Redis outage/recovery and concurrent read/write consistency across replicas.
- Performance of publication-cleanup changes in the current checkout.

Use the [runbook](RUNBOOK.md) to capture new results separately. Do not overwrite historical logs.
