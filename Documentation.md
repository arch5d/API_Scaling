High-Throughput Blog Platform: Systems Engineering & Benchmarking Plan
Framing: throughput as a moving target, not a fixed number

> Older work stamps below are historical records of each phase. Where they conflict with the final
> 2026-11-19 stamp above, the final stamp is authoritative.

## Work Stamp - 2026-11-19 (final)

### Achieved

- Added PgBouncer in transaction-pooling mode between the API tier and PostgreSQL. The API connects to `pgbouncer:6432`; PgBouncer uses `max_client_conn=1000` and `default_pool_size=20`. With eight API replicas, `SHOW POOLS` reported 8 client connections and 5 server connections, while PostgreSQL reported 11 total connections against a 100-connection limit.
- Added HTTP caching to `GET /articles/:id`: `ETag` derived from the article id and `updated_at`, `Cache-Control: public, max-age=60, stale-while-revalidate=30`, and `304 Not Modified` with an empty body when `If-None-Match` matches.
- Added cache-fill stampede protection: an in-process Promise map coalesces concurrent misses in one replica, and a Redis `SET NX PX 5000` lock with a token-checked Lua release deduplicates fills across replicas. Waiters poll the cache for up to 2 seconds before falling back to PostgreSQL.
- Extended the unit suite to 25 tests: ETag/304/Cache-Control behaviour and a concurrency test proving two simultaneous misses cause one database query. `npm test`, `npm run lint` and `npm run format:check` all pass.
- Re-ran the acceptance workload on the final code with eight replicas: a 2-minute plateau via the Compose network passed (p95 5.56 ms, p99 9.48 ms, zero drops), and a **full 10-minute plateau through the published port from a Linux bridge network passed all thresholds** — 0 dropped iterations, 0.00% HTTP failures, p95 11.70 ms, p99 27.95 ms, 522,009 cache hits / 2,848 misses, 663,132 requests (921.10 requests/sec aggregate over ramp + plateau + cooldown), max 36/300 VUs. Raw output: `benchmarks/stress-published-linuxvm-10m.log`.
- Confirmed that a true native-Linux-host run is not possible on this machine (only Docker Desktop's WSL utility distro is installed). The Compose-network run and the Linux bridge published-port run both stay inside Docker's Linux VM and exercise Linux networking without the Windows host forward.

### Current Status

All originally remaining goals are complete: 1,000 iterations/sec is sustained for 10 minutes on the final code, Postgres connections are pooled for larger replica counts, and HTTP caching/stampede protection are implemented and tested. Two later 10-minute attempts were discarded because the host session timed out mid-run and orphaned the k6 containers; their logs are marked incomplete in `benchmarks/PROGRESS.md`.

### To Test

1. Scale beyond eight replicas when more CPU is available; PgBouncer `default_pool_size` may need to increase for write-heavy traffic.
2. Repeat the Windows-host published-port test on a native Linux host if that deployment is required.
3. Commit the working-tree changes and benchmark evidence when approved.

## Work Stamp - 2026-11-19

### Achieved

- Started the three-replica stack on Docker Engine 29.5.3 and confirmed all replicas healthy, Redis ready, and 229,346 articles in PostgreSQL.
- Isolated the previous 1,000-RPS failures to the client/connect path: an identical k6 run through the Compose network (`BASE_URL=http://nginx`) passed with zero dropped iterations and 0.00% failures.
- **Completed the full 10-minute 1,000-iterations/sec acceptance through NGINX on the Compose network:** 0 dropped iterations, 0.00% HTTP failures, p95 7.78 ms, p99 27.16 ms, 521,896 cache hits and 2,891 misses across 662,890 requests (920.78 requests/sec averaged over the ramp, plateau and cooldown). At most 196 of 300 preallocated VUs were needed. Raw output: `benchmarks/stress-internal-10m.log`.
- Traced the remaining host-path drops to `host.docker.internal` and Docker's userland proxy. With `"userland-proxy": false` in the Docker daemon config and `BASE_URL=http://127.0.0.1:3000`, the 2-minute plateau passed with 0 drops, 0.00% failures, p95 10.93 ms and p99 34.81 ms. A full 10-minute host run still dropped 287 iterations with 0.00% HTTP failures, so the published-port path remains client-limited on this machine; the Compose-network acceptance is the valid final measurement.
- Stopped one API replica during a 2-minute 1,000-RPS plateau. All thresholds passed: 0 dropped iterations, 0.00% HTTP failure rate (one in-flight request failed at the stop), p95 5.54 ms and p99 18.70 ms.

### How It Was Achieved

No application code changed for this phase. The stack already had the tuned NGINX worker/keepalive
settings, the API HTTP keep-alive hook, the corrected create-then-delete write mix, and the
realistic Pareto access pattern. The work was to control the load-generator environment: run k6
with 8 CPU/8 GB, flush Redis before each run, target the Compose network for the clean acceptance
measurement, and remove the Windows host connect-path overhead for the published-port retest.

### Current Status

The 1,000 iterations/sec plateau is now a **passing 10-minute measurement** for the three-replica,
cache-enabled deployment behind NGINX, with large latency headroom against the p95 <250 ms,
p99 <500 ms, <1% errors and zero-drop contract. The reported 920.78 requests/sec is the average
over the whole 12-minute scenario including ramp-up and cooldown, not the plateau rate.

### To Test

1. ~~Full 10-minute plateau through the published port with `userland-proxy: false`.~~ Tested: 287 dropped iterations with 0.00% HTTP failures. Not the acceptance path on this host.
2. ~~Stop one API replica during the sustained plateau and verify all thresholds still pass.~~ Done.
3. Update the README run commands to use `127.0.0.1:3000`, then commit the tuning changes and benchmark evidence when approved.

All raw k6 summaries and the reproduction commands are in `benchmarks/` (`PROGRESS.md`, `RUNBOOK.md`).

## Work Stamp - 2026-09-14

### Achieved

- Defined a realistic first contract: 100 RPS, fewer than 1% errors, p95 below 250 ms, and p99 below 500 ms.
- Built a Fastify REST API for article CRUD with request validation, pagination, health checks, structured logging, and graceful shutdown.
- Added PostgreSQL persistence with a bounded connection pool, indexes, Docker Compose setup, and reproducible 100,000-article seed data.
- Added a k6 arrival-rate workload using 80% single-article reads, 15% list reads, and 5% writes.
- Verified the PostgreSQL-only baseline at 100 RPS for the planned run. The baseline passed the latency and error thresholds.
- Added Redis cache-aside behavior for `GET /articles/:id`, a 10-minute TTL, write invalidation, `X-Cache` headers, and PostgreSQL fallback when Redis is unavailable.
- Verified cache behavior with `MISS` followed by `HIT` and passed the corrected smoke workload with 0% failed requests, p95 13.41 ms, and p99 40.03 ms.
- Added Prometheus-compatible `/metrics`, replica-aware `/health`, a Docker image, and NGINX reverse proxy deployment.
- Started and validated three healthy API replicas behind NGINX; requests reached all three replica hostnames.
- Added a root `GET /` service-information endpoint so `http://localhost:3000/` is not a 404.

### How It Was Achieved

The work progressed in controlled phases: first establish a database-backed baseline, then add Redis and a realistic access pattern, then add metrics and three API replicas behind NGINX. Docker supplies PostgreSQL, Redis, the API replicas, NGINX, and k6; each benchmark isolates a specific scaling change.

### Current Status

The corrected cache benchmark passed the 100-RPS acceptance thresholds with 0% failed requests in the smoke validation. The controlled hot-read stress test then reached its configured 1,000 iterations/sec plateau for two minutes and completed successfully. Across the full three-minute ramp, plateau, and cooldown, it recorded 93,899 iterations and 94,824 HTTP requests, so the aggregate rates were 521.7 iterations/sec and 526.8 HTTP requests/sec; these averages include the cooldown and are not the peak rate.

Stress metrics: p95 5.13 ms, p99 8.88 ms, 0% failed requests, 75,204 cache hits, and 2 cache misses. This demonstrates that one cache-enabled API process handled the short 1,000-iterations/sec hot-read stress target under the current local workload. It is not yet a 10-minute production-capacity claim.

The earlier 4 GB stress attempt reached the 1,000 iterations/sec plateau with 0% HTTP failures, p95 5.43 ms, p99 16.43 ms, but recorded 212 dropped iterations. It was therefore not a clean sustained-arrival pass. The rerun used an 8 GB, 8-CPU k6 container, the realistic full-dataset access pattern, an empty Redis cache, and the zero-drop threshold. That command completed with exit code 0, so the realistic 1,000-RPS acceptance test passed. The exact final p95, p99, cache-hit, cache-miss, and resource totals were not retained in the terminal record and must not be reconstructed from the earlier artificial hot-read run.

This validates the cache-enabled API and its local three-replica deployment under the tested workload; it does not constitute a production-capacity guarantee. The measured target is a benchmark result on this machine, not a universal capacity guarantee.

### Replicated Deployment Result

Added Prometheus-compatible `/metrics`, replica-aware `/health`, a Node.js API Docker image, and an NGINX reverse proxy. The Compose deployment was started with three healthy API replicas. Requests through `http://localhost:3000` reached all three distinct container hostnames, and `/metrics` returned HTTP 200. Each replica has `DB_POOL_MAX=10`, giving a maximum application pool budget of `3 x 10 = 30` PostgreSQL connections. PgBouncer is not yet included.

The replicated smoke workload passed with 0% HTTP failures, zero dropped iterations, p95 10.86 ms, p99 19.55 ms, 622 cache hits, and 77 misses. Stopping one replica during 300 health requests also produced 300/300 successful responses. The first full realistic 1,000-RPS run through NGINX did not pass: it recorded 26,262 dropped iterations, 1.80% HTTP failures, p95 780.57 ms, and p99 4.63 s. NGINX was then tuned with 4,096 worker connections, upstream keepalive, multiple workers, and explicit proxy timeouts.

### Replica-Failure Test During Sustained Load

The 300-health-request replica-failure result was preserved and extended to a failure during load. A smoke workload (ramping to 30 iterations/s) was run through NGINX, and one of the three API replicas was stopped at the 20-second mark, during the sustained plateau. The run passed every acceptance threshold: zero dropped iterations, 0.00% HTTP failures, p95 12.41 ms, p99 15.43 ms, 839 iterations, and 852 HTTP requests with a 100% check success rate.

### NGINX Tuning Retest

The retest after the NGINX concurrency tuning (4,096 worker connections, upstream keepalive 256, multiple workers, explicit proxy timeouts) still did not meet the acceptance thresholds. The full realistic 1,000-RPS run through `http://localhost:3000` recorded 20,651 dropped iterations, 1.18% HTTP failures, p95 574.18 ms, p99 1.03 s, and 293,249 cache hits against 2,044 misses across 376,898 HTTP requests (373,248 iterations, 547.99 requests/sec average).

NGINX access logs show the proxy kept answering HTTP 200/201/204 for every connection it accepted for the entire run; the k6 failures are TCP connect-phase timeouts ("dial: i/o timeout" at roughly 30 s) before a connection is established. The bottleneck in the failed runs is therefore in the connection accept/forward path between Docker Desktop on Windows and the published NGINX port, not in the API replicas or the tuned NGINX worker settings. On this local Docker Desktop deployment, replicated 1,000-RPS acceptance is not yet demonstrated; the passing single-instance run remains the reference for cache-enabled capacity.

### Remaining Work

1. Preserve the final k6 summary from the successful realistic 1,000-RPS single-instance run. The original terminal output was lost and cannot be reconstructed; instead the summaries of the two NGINX-pointed stress runs (the initial failure and the post-tuning retest) are now preserved in the record above.
2. Rerun the realistic workload through `http://localhost:3000` after the NGINX concurrency tuning. Executed on 2026-09-14; it did not pass (20,651 dropped iterations, 1.18% HTTP failures, p95 574.18 ms, p99 1.03 s). Next bottleneck to test: the TCP connect/forward path on Docker Desktop (host accept backlog, userland-proxy, or re-testing on Linux networking), after which the run must be repeated against the zero-drop, <1% error, p95 < 250 ms, p99 < 500 ms contract.
3. Preserve the 300-request replica-failure result and extend it to a failure test during sustained load. Completed: stopping one replica mid-run produced zero dropped iterations and 0.00% failures.

The load test supports `ACCESS_PATTERN=realistic`, which samples article IDs with a Pareto distribution across the full 100,000-article dataset. This creates a natural hot set and long tail without preloading Redis or restricting requests to a tiny set of articles. Redis must be flushed before the run so the cache warms from traffic.

The first hot-read stress attempt was artificially concentrated on 100 articles and is not a production-capacity result. The realistic full-dataset rerun completed successfully with the better-provisioned generator and zero-drop threshold. Numeric final metrics remain unrecorded because the terminal output was not retained.

## First Decision: What Is Realistic?

Do not start by promising 1,000 RPS. RPS is only meaningful together with a workload, latency target, error budget, payload size, and database shape. A read from Redis and a write that validates data, updates PostgreSQL, and invalidates a cache are different workloads and must be measured separately.

For the first implementation, use this deliberately modest contract:

- **Deployment:** one application process on a local or small 4-core machine; PostgreSQL runs locally or on a nearby development instance.
- **Workload:** 80% `GET /articles/:id`, 15% `GET /articles`, and 5% writes split between `POST`, `PUT`, and `DELETE`.
- **Data:** at least 100,000 articles, realistic response sizes, and a fixed test dataset that can be recreated.
- **Initial acceptance point:** sustain 100 RPS for 10 minutes with fewer than 1% errors, p95 latency below 250 ms, and p99 below 500 ms.
- **Stretch milestone:** test 1,000 RPS only after the baseline is stable. It is a measurement milestone, not an assumed requirement.

These numbers are starting assumptions, not universal limits. Change them when the intended users, traffic pattern, or product SLO is known. The first benchmark should produce the baseline; optimization comes after the baseline is reproducible.

### Capacity Intuition

Use Little's Law to sanity-check load-test results:

`concurrency = throughput x average latency`

At 100 RPS and 100 ms average latency, the service needs roughly 10 requests in flight. At 1,000 RPS and 250 ms average latency, it needs roughly 250 requests in flight. A test that uses too few clients cannot generate the requested rate, so a reported "1,000 RPS limit" may only be a client-side limit.

### What We Build First

Before Redis, clustering, or a load balancer, implement and benchmark the smallest complete vertical slice:

1. A Node.js API with health checking, request validation, structured logging, and graceful shutdown.
2. PostgreSQL migrations and indexes for the article queries.
3. A bounded `pg.Pool`; never open a database connection per request.
4. The article CRUD endpoints with pagination on `GET /articles`.
5. A k6 test that drives the workload above and reports throughput, p95/p99 latency, and errors.

Only after this baseline passes its acceptance point should we add caching. Each later phase must rerun the same test so that an improvement is measured rather than assumed.

### Baseline Result

The PostgreSQL-only baseline sustained 100 RPS and passed the latency and error thresholds. The first Redis run sustained the same requested rate with p95 10.19 ms, p99 36.16 ms, and 0.19% failed requests, but that result is provisional: the original load test reused DELETE targets and produced false 404s. The load test now creates an article immediately before deleting it; rerun the full test before using the Redis result for comparison.

A standard CRUD blog is trivial. Designing one to saturate whatever request rate the underlying hardware can sustain is a systems engineering and benchmarking exercise - because the ceiling isn't a constant; it moves as you remove bottlenecks (naive DB queries, single-threaded runtimes, missing indexes, no caching, single-core execution).

Rather than targeting a fixed number like "1,000 RPS," this plan treats each phase as raising the throughput ceiling on the same hardware and measuring the new ceiling with a proper load test, instead of assuming it. On modest hardware (e.g., a 4-core cloud VM), realistic order-of-magnitude ranges look like:

Phase	Bottleneck removed	Typical ceiling (4-core box, illustrative)
1 - Naive baseline	none	Tens to low hundreds of RPS before latency/error spikes
2 - DB + pooling hardened	slow queries, connection exhaustion	Several hundred to low thousands of RPS on reads
3 - Redis caching	DB round-trips on hot reads	Low thousands to tens of thousands of RPS on cached reads
4 - Horizontal + LB	single-core ceiling	Scales roughly linearly with cores/instances, until network or DB write-path becomes the limiter

These numbers are illustrative, not promises - actual results depend entirely on hardware, payload size, and query complexity. The point of each phase is to run the benchmark, record the real number, then move to the next bottleneck.

Core Architecture & Tech Stack
Backend Engine: Node.js - event-loop non-blocking I/O, horizontally scaled via cluster/PM2/containers
Primary Database: PostgreSQL
In-Memory Cache: Redis
Load Balancer / Reverse Proxy: NGINX or Caddy
Load Testing & Observability: k6 or Locust for load generation; Prometheus + Grafana (or a lightweight APM) for metrics
Phased Engineering Roadmap
Phase 1 - The Baseline (Naive Implementation)

Build standard RESTful endpoints:

POST   /articles
GET    /articles/:id
GET    /articles
PUT    /articles/:id
DELETE /articles/:id

Run as a single Node process, connected directly to Postgres, no indexes, no cache.

Benchmark: Use k6 with a ramping-arrival-rate executor (not just virtual users - see note below) to ramp request rate upward until latency and error rate blow up. Record the actual ceiling RPS, p95/p99 latency, and where it breaks (CPU saturation, connection pool exhaustion, event-loop blocking).

Why arrival-rate, not just VUs: a plain VU-based k6 scenario controls concurrency, not throughput - under a slow naive implementation, 1,000 VUs might only generate a few hundred actual requests/sec, because each VU is stuck waiting on a slow response. constant-arrival-rate / ramping-arrival-rate executors let you drive a specific request rate independent of how fast the server responds, which is what you actually want to find a breaking point.

Phase 2 - Database & Concurrency Hardening
Add B-Tree indexes on slug, created_at, and foreign keys.
Tune the Node Postgres pool (pg.Pool): max, min, idleTimeoutMillis, connectionTimeoutMillis.
Strip ORM overhead on hot read paths - use pg (node-postgres), postgres.js, or knex/Prisma dropped to raw SQL where the ORM's query-building overhead matters.

Benchmark: Re-run the same ramping load test; compare the new ceiling RPS and p95/p99 latency against Phase 1's numbers.

Phase 3 - Multi-Layer Caching Strategy
Cache-Aside with Redis: store serialized article JSON with a reasonable TTL (5–15 min).
Invalidate on write: clear the relevant cache key(s) on PUT/DELETE.
HTTP caching, as two distinct mechanisms:
ETag - a separate response header (not a Cache-Control directive). Client echoes it via If-None-Match; server returns 304 Not Modified with no body if the resource hasn't changed.
Cache-Control: stale-while-revalidate - an actual Cache-Control directive, e.g. Cache-Control: max-age=60, stale-while-revalidate=30, letting the client serve a stale copy instantly while revalidating in the background.

Benchmark: /articles/:id reads should now serve primarily from Redis, dropping response times to single-digit milliseconds and pushing the throughput ceiling well past Phase 2.

Phase 4 - Horizontal Concurrency & Load Balancing
Run multiple backend instances across CPU cores - Node's built-in cluster module, PM2 cluster mode, or multiple container replicas.
Place NGINX (or Caddy) in front as a reverse proxy, round-robin or least-connections.
Tune keep-alive and worker connection limits for efficient connection reuse.
Re-check the DB connection budget: N app instances × pool size can exceed Postgres's max_connections (default 100) fast - e.g. 8 instances × 20 connections = 160. Add PgBouncer in transaction-pooling mode between the app tier and Postgres once you're running multiple instances, or you'll trade "connection starvation" for "Postgres refusing connections."

Benchmark: throughput ceiling should scale close to linearly with core/instance count until the DB write path, network, or PgBouncer itself becomes the new limiter - at which point that becomes the next phase to attack.

Key Failure Modes to Test & Mitigate
Challenge	Failure mode under heavy load	Mitigation
Cache Stampede / Dogpiling	A popular post's cache entry expires and a large burst of concurrent requests hits the DB simultaneously	In a single instance: deduplicate concurrent requests for the same key via a shared in-flight Promise (request coalescing). Across multiple instances (Phase 4+): a Redis-based distributed lock (SET NX PX, or a library like redlock/redis-semaphore), or soft TTLs with background revalidation
DB Connection Starvation	Opening a fresh connection per request exhausts file descriptors / Postgres connection slots	Strict, tuned connection pooling (pg.Pool limits) per instance, plus PgBouncer once multiple instances are in play
N+1 Query Problem	Fetching a list of 20 posts + authors triggers 21 separate queries per request	Use SQL JOINs or batch-fetch related data in one round trip
JSON Serialization Bottlenecks	High CPU overhead serializing large payloads under concurrent load	Select only needed fields (SELECT id, title, summary) for list views; avoid returning full article bodies on index routes; consider a schema-based serializer (e.g. Fastify's) over generic JSON.stringify
Additional Recommendations
Framework choice: consider Fastify over Express for the baseline - its schema-based JSON serialization is meaningfully faster under concurrent load than Express + generic JSON.stringify, which directly helps the JSON-serialization failure mode above.
Logging: use a non-blocking logger (pino) instead of synchronous console.log - synchronous logging is a common, easy-to-miss throughput killer under load.
Graceful shutdown: handle SIGTERM to drain in-flight requests before an instance exits - once you're running multiple instances behind NGINX (Phase 4), deploys/restarts without this will show up as spurious errors in your load tests.
Report the real ceiling, not a target: at the end of each phase, the deliverable is the measured maximum sustainable RPS on your actual hardware (with p95/p99 latency and error rate at that point) - not a claim that a fixed number was hit.