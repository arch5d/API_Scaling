# Benchmark results — 19 November 2026

This is the historical experiment record. Raw logs are retained unchanged, including failed and incomplete runs. Workload arrival rate and HTTP throughput are different units.

For fresh measurements with captured hardware, source provenance, and controlled cache/pool/replica comparisons, see the [24 November experiment](CURRENT.md). The missing historical measurements below remain missing; new runs are not substitutes for historical evidence.

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

## Recovered session evidence

On 21 November 2026, the repository owner supplied an OpenCode recovery report from the persisted session titled “Current project details” (1–19 November 2026). This section summarizes that supplied report; the underlying session history was not independently inspected here. References to current repository prose in the report are not new historical measurements.

On 24 November, the owner supplied a follow-up OpenCode report stating that the persisted history had now been inspected directly, including the November session and a September session. That inspection confirmed the missing historical hardware capture, the lost original single-instance summaries, and the absence of controlled Redis/PgBouncer comparisons. This repository records the supplied verification; it does not claim that the documentation editor independently accessed those sessions. The follow-up cites November sequence 4 and September sequence 56 as acknowledging the missing single-instance output. No new raw benchmark result was recovered.

The report found no benchmark-time Docker VM CPU/RAM allocation, host CPU model, physical/logical core counts, or installed RAM. The separate 21 November Docker check (12 logical CPUs, 12,389,126,144 bytes of memory) describes the current environment only.

Historical command excerpts cited by the report establish the generator topology:

- Session sequence 218: `docker run --rm -i --cpus=8 --memory=8g --network api_scaling_default … -e BASE_URL=http://nginx -e STRESS=true -e ACCESS_PATTERN=realistic …` for the accepted three-replica run, before PgBouncer.
- Session sequence 1036: `docker run --rm -i --cpus=8 --memory=8g --network bench-external … -e BASE_URL=http://host.docker.internal:3000 …` for the accepted eight-replica run.

These excerpts are incomplete provenance snippets, not executable commands. Both generators shared the Docker Desktop VM and physical machine with the stack. The report also states that Redis was flushed before both accepted runs. Neither a different bridge nor the k6 container's resource limits establish dedicated hardware.

Earlier single-instance experiments appear only in session recaps, with original output missing:

| Recalled experiment                        | Reported result                                                                                                   | Evidence limitation                                                                                                                |
| ------------------------------------------ | ----------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| PostgreSQL-only baseline                   | “sustained 100 RPS”, latency/error thresholds passed                                                              | No retained raw log, percentiles, absolute counts, drops, or verified request/iteration distinction                                |
| Single-instance hot reads with Redis       | 521.7 iterations/s; 526.8 HTTP requests/s; p95 5.13 ms; p99 8.88 ms; reported 0% failures; 75,204 hits / 2 misses | Session recap only; duration, absolute failures/total requests, drops and full configuration not retained in the supplied evidence |
| Single-instance realistic reads with Redis | Reported exit code 0 with initially empty Redis                                                                   | Exact summary lost; the recap's “1,000 RPS” label does not establish measured HTTP throughput                                      |
| Earlier provisional 100-iteration/s run    | p95 10.19 ms; p99 36.16 ms; reported 0.19% failures                                                               | Original output and complete comparison context missing                                                                            |

These recollections are not verified November 19 results and are excluded from the README's numerical comparison and visuals. They do not establish a Redis speedup. The recovery found no controlled comparison changing only Redis or only PgBouncer; replica count, network path and implementation changes remain confounded in the accepted runs.

## Unmeasured questions

- Maximum sustainable rate, with repeated runs and uncertainty estimates.
- Replica scaling with fixed hardware, network, dataset, and code.
- Uniform versus skewed reads under identical conditions.
- Redis outage/recovery and concurrent read/write consistency across replicas.
- Performance of publication-cleanup changes in the current checkout.

Use the [runbook](RUNBOOK.md) to capture new results separately. Do not overwrite historical logs.
