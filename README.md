# API scaling baseline

This is the measurable blog API and scaling deployment. It supports PostgreSQL with PgBouncer transaction pooling, Redis cache-aside reads with conditional HTTP caching and stampede protection, Prometheus metrics, and multiple API replicas behind NGINX.

## Replicated deployment

Build and start three API replicas behind NGINX (PgBouncer, PostgreSQL and Redis start automatically):

```powershell
docker compose up -d --build --scale api=3 api nginx
```

To demonstrate scaling past the direct-connection budget, use more replicas:

```powershell
docker compose up -d --scale api=8
```

Use the proxy at `http://localhost:3000`. Verify readiness and metrics:

```powershell
Invoke-RestMethod http://localhost:3000/health
Invoke-WebRequest -UseBasicParsing http://localhost:3000/metrics | Select-Object StatusCode
```

The root endpoint is `http://localhost:3000/` and returns service links for health, metrics, and articles.

Each API replica uses `DB_POOL_MAX=10` **client** connections to PgBouncer. PgBouncer uses transaction pooling with `max_client_conn=1000` and `default_pool_size=20`, so eight replicas can open up to 80 client connections while PgBouncer holds only 20 server connections to PostgreSQL (`max_connections=100`). Inspect the pools with:

```powershell
docker exec -e PGPASSWORD=api api_scaling-pgbouncer-1 psql -h 127.0.0.1 -p 6432 -U api -d pgbouncer -c "SHOW POOLS;"
```

PgBouncer uses `auth_type=plain` because it is only reachable on the internal Compose network; use TLS and SCRAM for a production deployment.

`GET /articles/:id` also returns `ETag` and `Cache-Control: public, max-age=60, stale-while-revalidate=30`. Send the ETag back as `If-None-Match` to receive `304 Not Modified` with no body. Concurrent cache misses are coalesced in-process and guarded across replicas by a Redis fill lock.

## Run locally

1. Start PostgreSQL and seed 100,000 articles:

   ```powershell
   docker compose up -d postgres redis
   ```

2. In a second terminal, set the database URL and start the API:

   ```powershell
   $env:DATABASE_URL = 'postgres://api:api@localhost:5432/api_scaling'
   $env:REDIS_URL = 'redis://localhost:6379'
   npm start
   ```

3. Check readiness for a standalone local process:

   ```powershell
   Invoke-RestMethod http://localhost:3000/health
   ```

4. Run the baseline workload with k6:

   ```powershell
   k6 run loadtest/baseline.js
   ```

   If k6 is not installed on Windows, run it through Docker instead:

   ```powershell
   docker run --rm -i --network host -v "${PWD}\loadtest:/scripts" -e BASE_URL=http://127.0.0.1:3000 grafana/k6 run /scripts/baseline.js
   ```

   Validate the workload quickly before the full run:

   ```powershell
   docker run --rm -i --network host -v "${PWD}\loadtest:/scripts" -e BASE_URL=http://127.0.0.1:3000 -e SMOKE=true grafana/k6 run /scripts/baseline.js
   ```

Use `127.0.0.1` rather than `host.docker.internal` on Docker Desktop: the latter measurably increases connect overhead under stress. For the published-port stress test, set `"userland-proxy": false` in `%USERPROFILE%\.docker\daemon.json` and restart Docker Desktop. See `benchmarks/RUNBOOK.md`.

The PostgreSQL baseline achieved 100 RPS. For the cache phase, warm one article with two requests and verify the second response has `X-Cache: HIT`:

```powershell
Invoke-WebRequest http://localhost:3000/articles/1 | Select-Object StatusCode,Headers
Invoke-WebRequest http://localhost:3000/articles/1 | Select-Object StatusCode,Headers
```

The cache-enabled run completed at about 100 iterations/sec for 10 minutes with p95 10.19 ms, p99 36.16 ms, and 0.19% failed requests. That result is provisional because the earlier benchmark reused DELETE targets; the workload now creates an article immediately before deleting it to avoid false 404 failures. Rerun the full benchmark with the corrected script before treating the result as final.

For a realistic cache workload, use `-e ACCESS_PATTERN=realistic`. This samples IDs across the full 100,000-article dataset with a Pareto distribution: popular articles are requested more often, while the long tail is still exercised. Redis must be empty before the run so entries warm naturally; do not preload the cache.

Clear Redis and verify the API first:

```powershell
docker exec api_scaling-redis-1 redis-cli FLUSHDB
Invoke-RestMethod http://127.0.0.1:3000/health
```

Then run k6 with more CPU, memory, VUs, and a zero-drop acceptance threshold:

```powershell
docker run --rm -i --cpus=8 --memory=8g --network host `
   -v "${PWD}\loadtest:/scripts" `
   -e BASE_URL=http://127.0.0.1:3000 `
   -e STRESS=true `
   -e ACCESS_PATTERN=realistic `
   grafana/k6 run /scripts/baseline.js
```

The single-instance improved 8 GB k6 run completed with exit code 0 using the realistic full-dataset access pattern and zero-drop threshold. Earlier three-replica runs through NGINX did not pass (26,262 dropped iterations / 1.80% HTTP failures before tuning; 20,651 / 1.18% after NGINX tuning). NGINX kept serving every accepted connection, so the failures were k6 connect-phase timeouts on the Docker Desktop path rather than API errors. A replica stopped during a 30 RPS smoke load produced zero dropped iterations and 0.00% failures.

The 1,000-RPS goal is demonstrated. A full 10-minute plateau on the Compose network with three replicas completed with **0 dropped iterations, 0.00% HTTP failures, p95 7.78 ms and p99 27.16 ms** (662,890 requests at 920.78 requests/sec averaged over ramp + plateau + cooldown). The final code — with PgBouncer, ETag caching and fill-lock coalescing — passed a full 10-minute plateau through the **published port from a Linux bridge network** with eight replicas: **0 dropped, 0.00% HTTP failures, p95 11.70 ms, p99 27.95 ms**, 522,009 cache hits / 2,848 misses, 663,132 requests at 921.10 requests/sec aggregate. Stopping one replica during a 1,000-RPS plateau also passed all thresholds: 0 dropped, 0.00% HTTP failure rate (one in-flight request at the moment of stop), p95 5.54 ms and p99 18.70 ms. On the Windows host network path, use `127.0.0.1` and disable the userland proxy for short runs; 10-minute host runs still drop a small number of iterations. Raw results and reproduction steps are in `benchmarks/`.

Stress mode now preallocates 300 VUs and allows up to 1,000 VUs. The larger Docker allocation gives k6 headroom to maintain the arrival rate without dynamically allocating VUs during the plateau.

## API

- `GET /health`
- `GET /metrics`
- `GET /`
- `GET /articles?limit=20&offset=0`
- `GET /articles/:id`
- `POST /articles`
- `PUT /articles/:id`
- `DELETE /articles/:id`

`DB_POOL_MAX` is intentionally bounded. With three replicas the client budget is `3 x 10 = 30` connections to PgBouncer; with eight replicas it is `80`. PgBouncer caps actual PostgreSQL server connections at `default_pool_size=20`. Recalculate both budgets whenever replica count or pool size changes.
