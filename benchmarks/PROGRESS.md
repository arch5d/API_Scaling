# Benchmark progress log (2026-11-19)

Live record of the scaling work. Raw k6 output lives in this folder next to this file.

## Environment

- Docker Engine 29.5.3, API replicas behind NGINX, Redis flushed before stress runs.
- PostgreSQL holds 229,346 articles (100,000 seed rows plus earlier write-phase rows).
- k6 workload: `loadtest/baseline.js`, `STRESS=true`, `ACCESS_PATTERN=realistic`, 8 CPU / 8 GB,
  300 preallocated VUs, max 1,000 VUs, zero-drop threshold.
- Final code adds PgBouncer transaction pooling, ETag / `stale-while-revalidate` headers, and
  Redis-lock + in-process coalescing for cache fills.

## Results

| Test                                                                                               | Target        | Result                                                                                                                                        | Verdict          |
| -------------------------------------------------------------------------------------------------- | ------------- | --------------------------------------------------------------------------------------------------------------------------------------------- | ---------------- |
| Smoke via Compose network                                                                          | 30 iters/s    | 0 dropped, 0.00% failures, p95 8.74 ms, p99 13.55 ms                                                                                          | PASS             |
| 2 min plateau via Compose network                                                                  | 1,000 iters/s | 0 dropped, 0.00% failures, p95 7.71 ms, p99 21.83 ms                                                                                          | PASS             |
| Full 10 min plateau via Compose network (3 replicas, pre-PgBouncer)                                | 1,000 iters/s | 0 dropped, 0.00% failures, p95 7.78 ms, p99 27.16 ms, 662,890 requests, max 196/300 VUs                                                       | **PASS**         |
| Windows published port via `host.docker.internal`                                                  | 1,000 iters/s | 729 dropped, 0.00% failures, p95 73.12 ms, VUs grew to 553                                                                                    | FAIL (zero-drop) |
| Windows published port via `127.0.0.1`, with and without userland proxy                            | 1,000 iters/s | 2 min: PASS; 10 min: 282–287 dropped, 0.00% failures                                                                                          | FAIL at 10 min   |
| Replica stopped during 2 min plateau                                                               | 1,000 iters/s | 0 dropped, 0.00% failure rate (1 in-flight request), p95 5.54 ms, p99 18.70 ms                                                                | PASS             |
| **Published port from k6 on a Linux bridge network inside the Docker VM (8 replicas, final code)** | 1,000 iters/s | 0 dropped, 0.00% failures, p95 11.70 ms, p99 27.95 ms, 522,009 hits / 2,848 misses, 663,132 requests (921.10 req/s aggregate), max 36/300 VUs | **PASS — final** |
| 2 min plateau, 8 replicas via Compose network                                                      | 1,000 iters/s | 0 dropped, 0.00% failures, p95 5.56 ms, p99 9.48 ms, max 8/300 VUs                                                                            | PASS             |

### PgBouncer verification

- `SHOW POOLS` with 8 replicas: 8 client connections, 5 server connections, `pool_mode=transaction`.
- Postgres reported 11 total connections, far below `max_connections=100`. Previously 8 replicas
  would have required 80 direct connections.
- API connects to `postgres://api:api@pgbouncer:6432/api_scaling`; PgBouncer has a healthcheck and
  the API waits for it before starting.

### HTTP caching / stampede verification

- 25 unit tests pass, including: ETag header, `Cache-Control: public, max-age=60,
stale-while-revalidate=30`, 304 with empty body on `If-None-Match`, and two concurrent misses
  coalescing into one database query.
- Live check through NGINX: first request `X-Cache: MISS`, second `HIT`, conditional request with
  matching `If-None-Match` returned 304 with no body.
- Fill deduplication uses a local in-flight Promise map plus a Redis `SET NX PX 5000` lock with
  token-checked Lua release; waiters poll the cache for up to 2 s before falling back to Postgres.

### Notes on discarded runs

- `stress-host-noproxy-500vu-10m.log` and `stress-final-3replicas-10m.log` are incomplete: the host
  session timed out and the orphaned k6 containers were removed. They are not valid results and
  must not be used for comparisons.
- A one-off `pg` pool connection-timeout cluster appeared in API logs during an earlier Windows-host
  run; later runs had 0% HTTP failures and no connection exhaustion.

## To test next

1. Scaling beyond 8 replicas once more CPU is available; PgBouncer `default_pool_size` may need
   tuning above 20 for write-heavy workloads.
2. A real Linux host (none is installed here; only Docker Desktop's WSL utility distro) if the
   Windows published-port path is required for production acceptance.
3. Commit the working-tree changes and benchmark results when approved.
