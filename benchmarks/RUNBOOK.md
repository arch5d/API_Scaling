# 1,000 RPS acceptance runbook

Exact commands used for the final benchmark phase (Windows + Docker Desktop, 2026-11-19).

## 1. Host tuning (Docker Desktop only)

On this machine `host.docker.internal:3000` added enough connect overhead to drop iterations at
1,000 RPS. Use `127.0.0.1:3000`, and disable the Docker userland proxy:

```powershell
# %USERPROFILE%\.docker\daemon.json — merge this key, do not replace the file
{ "userland-proxy": false }

docker desktop restart
```

Backup of the original config is kept as `daemon.json.bak`. Revert by restoring the backup and
restarting Docker Desktop if the host path is not needed.

## 2. Start the stack

```powershell
docker compose up -d --build --scale api=3
Invoke-RestMethod http://127.0.0.1:3000/health
```

Verify three healthy replicas and a ready cache. Flush Redis before every stress run so the
realistic Pareto access pattern warms the cache naturally:

```powershell
docker exec api_scaling-redis-1 redis-cli FLUSHDB
```

## 3. Full acceptance run (10-minute plateau, published port)

```powershell
docker run --rm -i --cpus=8 --memory=8g --network host `
  -v "${PWD}\loadtest:/scripts" `
  -e BASE_URL=http://127.0.0.1:3000 `
  -e STRESS=true `
  -e ACCESS_PATTERN=realistic `
  grafana/k6 run /scripts/baseline.js 2>&1 | Tee-Object -FilePath "benchmarks/stress-host-noproxy-10m.log"
```

Equivalent internal-network variant (avoids the published port entirely):

```powershell
docker run --rm -i --cpus=8 --memory=8g --network api_scaling_default `
  -v "${PWD}\loadtest:/scripts" `
  -e BASE_URL=http://nginx `
  -e STRESS=true `
  -e ACCESS_PATTERN=realistic `
  grafana/k6 run /scripts/baseline.js 2>&1 | Tee-Object -FilePath "benchmarks/stress-internal-10m.log"
```

Quick iteration: add `-e STRESS_PLATEAU=2m` (total run ~4 minutes instead of 12).

## 4. Acceptance contract

The k6 script fails the run if any threshold is crossed:

- `dropped_iterations count==0`
- `http_req_failed rate<0.01`
- `http_req_duration p(95)<250` and `p(99)<500`

The `ramping-arrival-rate` stages are 30 s ramp to 250, 1 min ramp to 1,000, 10 min at 1,000,
30 s ramp to 0. Aggregate `http_reqs/s` therefore includes ramp and cooldown and is **not** the
plateau rate; the plateau rate is the configured 1,000 iterations/sec.

## 5. Interpreting results

- `article_cache_hits` / `article_cache_misses` come from the `X-Cache` response header.
- `vus_max` well below 1,000 means the generator had headroom; a climbing VU count together with
  `dropped_iterations` indicates a client/connect-path limit, not an API limit.
- Raw k6 summaries for every run live next to this file.

## 6. Final code: PgBouncer + HTTP caching

PgBouncer is a Compose service. Check pooling after scaling replicas:

```powershell
docker compose up -d --scale api=8
docker exec -e PGPASSWORD=api api_scaling-pgbouncer-1 `
  psql -h 127.0.0.1 -p 6432 -U api -d pgbouncer -c "SHOW POOLS;"
docker exec api_scaling-postgres-1 psql -U api -d api_scaling -c "SELECT count(*) FROM pg_stat_activity;"
```

With 8 replicas this shows 8 client connections, 5 server connections and `pool_mode=transaction`.

Conditional requests:

```powershell
$r = Invoke-WebRequest -UseBasicParsing http://127.0.0.1:3000/articles/1
$r.Headers['ETag']                       # "1-2026-09-10T14:34:06.683Z"
$r.Headers['Cache-Control']              # public, max-age=60, stale-while-revalidate=30
node -e "fetch('http://127.0.0.1:3000/articles/1',{headers:{'If-None-Match':'$($r.Headers['ETag'])'}}).then(async r=>console.log(r.status,(await r.text()).length))"
```

## 7. Published-port acceptance from the Docker Linux VM

This path exercises Linux iptables port publishing without the Windows host forward. It is the
final accepted 10-minute run (8 replicas):

```powershell
docker network create bench-external
docker exec api_scaling-redis-1 redis-cli FLUSHDB
docker run --rm -i --cpus=8 --memory=8g --network bench-external `
  -v "${PWD}\loadtest:/scripts" `
  -e BASE_URL=http://host.docker.internal:3000 `
  -e STRESS=true `
  -e ACCESS_PATTERN=realistic `
  grafana/k6 run /scripts/baseline.js 2>&1 |
  Tee-Object -FilePath "benchmarks/stress-published-linuxvm-10m.log"
```

A true native-Linux-host run was not possible: this machine only has Docker Desktop's WSL utility
distro. The Compose-network run remains the closest Linux-native equivalent.

## 8. Replica-failure under sustained load

Start a 2-minute-plateau run as above in one terminal. At roughly 100 seconds (30 s + 60 s ramp
plus ~10 s into the plateau), stop one replica from another terminal:

```powershell
docker stop api_scaling-api-2
```

The run should still meet all thresholds; NGINX retries the failed upstream and `/health` reports
the remaining replicas. Restore the replica afterwards:

```powershell
docker compose up -d --scale api=3 api
```

Record the k6 summary in `benchmarks/replica-failure-under-load.log`.
