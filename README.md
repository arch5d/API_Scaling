# API scaling baseline

This is the measurable blog API and scaling deployment. It supports PostgreSQL, Redis cache-aside reads, Prometheus metrics, and multiple API replicas behind NGINX.

## Replicated deployment

Build and start three API replicas behind NGINX:

```powershell
docker compose up -d --build --scale api=3 api nginx
```

Use the proxy at `http://localhost:3000`. Verify readiness and metrics:

```powershell
Invoke-RestMethod http://localhost:3000/health
Invoke-WebRequest -UseBasicParsing http://localhost:3000/metrics | Select-Object StatusCode
```

The root endpoint is `http://localhost:3000/` and returns service links for health, metrics, and articles.

Each API replica uses `DB_POOL_MAX=10`. With three replicas, the application can open up to 30 PostgreSQL connections, before administrative or other connections. Keep this below PostgreSQL's configured connection budget; do not multiply replicas and pool size without checking it. The current Compose deployment does not include PgBouncer.

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
   docker run --rm -i --network host -v "${PWD}\loadtest:/scripts" -e BASE_URL=http://host.docker.internal:3000 grafana/k6 run /scripts/baseline.js
   ```

   Validate the workload quickly before the full run:

   ```powershell
   docker run --rm -i --network host -v "${PWD}\loadtest:/scripts" -e BASE_URL=http://host.docker.internal:3000 -e SMOKE=true grafana/k6 run /scripts/baseline.js
   ```

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
Invoke-RestMethod http://localhost:3001/health
```

Then run k6 with more CPU, memory, VUs, and a zero-drop acceptance threshold:

```powershell
docker run --rm -i --cpus=8 --memory=8g --network host `
   -v "${PWD}\loadtest:/scripts" `
   -e BASE_URL=http://host.docker.internal:3000 `
   -e STRESS=true `
   -e ACCESS_PATTERN=realistic `
   grafana/k6 run /scripts/baseline.js
```

The improved 8 GB k6 run completed with exit code 0 using the realistic full-dataset access pattern and zero-drop threshold. The current command targets the three-replica NGINX deployment on port 3000. Save the final numeric p95/p99/cache-counter summary from k6; do not use the earlier artificial 100-article hot-read metrics as a substitute.

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

`DB_POOL_MAX` is intentionally bounded. The current three-replica deployment uses a maximum application budget of `3 x 10 = 30` PostgreSQL connections. Recalculate this whenever replica count or pool size changes.
