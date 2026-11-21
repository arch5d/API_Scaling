# Running the load tests

Run these PowerShell commands from the repository root with Docker Compose. Tests create and update articles; deletes create their own target. Use a disposable benchmark database.

## Prepare

```powershell
docker compose up -d --build --scale api=3
docker compose restart nginx
Invoke-RestMethod http://localhost:3000/health
docker compose exec -T postgres psql -U api -d api_scaling -c "SELECT count(*) FROM articles;"
```

NGINX needs a reload or restart after replica addresses change. Wait for `/health` to succeed. A new PostgreSQL volume seeds IDs 1–100,000; existing volumes retain prior writes and do not rerun initialization.

Find the Compose network without assuming a checkout directory name:

```powershell
$apiId = docker compose ps -q api | Select-Object -First 1
$network = docker inspect --format '{{range $name, $config := .NetworkSettings.Networks}}{{$name}}{{end}}' $apiId
$scripts = (Resolve-Path ./loadtest).Path
```

This assumes the API's single default Compose network. Confirm the network if you customize Compose.

## Smoke test

```powershell
docker run --rm --network $network `
  -v "${scripts}:/scripts:ro" `
  -e BASE_URL=http://nginx -e SMOKE=true `
  grafana/k6 run /scripts/baseline.js
```

Smoke mode ramps to 30 iterations/second and lasts 35 seconds. Without `SMOKE` or `STRESS`, the scenario lasts 13 minutes with a 100-iteration/s plateau.

## Stress test

Clear only this project's disposable cache before a cold-cache run:

```powershell
docker compose exec -T redis redis-cli FLUSHDB
docker run --rm --cpus=8 --memory=8g --network $network `
  -v "${scripts}:/scripts:ro" `
  -e BASE_URL=http://nginx -e STRESS=true -e ACCESS_PATTERN=realistic `
  grafana/k6 run /scripts/baseline.js 2>&1 |
  Tee-Object -FilePath benchmarks/local-stress.log
if ($LASTEXITCODE -ne 0) { throw 'k6 failed; inspect the log.' }
```

Use a new log filename each time. The 8-CPU / 8-GB limits match the historical command, but available host resources still constrain k6. For a short run, add `-e STRESS_PLATEAU=2m`. Record any overrides to `PRE_VUS` or `MAX_VUS`.

Stress mode ramps from 10 to 250 iterations/s over 30 seconds, to 1,000 over one minute, holds for ten minutes, then ramps to zero over 30 seconds. Acceptance requires:

- Zero dropped iterations.
- HTTP failure rate below 1%.
- Whole-run p95 below 250 ms and p99 below 500 ms.

An iteration selects an operation: 80% single reads, 15% lists, 3% creates, 1% updates, and 1% create-then-delete operations in expectation. `realistic` is the script's name for a synthetic Pareto-like ID sampler with exponent 0.8, clamped at 100,000. It strongly favors the first few articles; it is not real user traffic. Without this option, reads sample IDs uniformly.

## Published-port comparison

The accepted historical eight-replica run originated from a separate Linux bridge inside Docker Desktop and targeted `host.docker.internal:3000`. It did not originate from Windows or a native Linux host. Current Compose ports bind to loopback for local development; that historical bridge-to-published-port route may not be reachable with this binding.

For a host-path measurement, use locally installed k6:

```powershell
k6 run -e BASE_URL=http://127.0.0.1:3000 -e STRESS=true -e ACCESS_PATTERN=realistic loadtest/baseline.js
```

Label the network path explicitly. Do not compare results as if only the API changed. Historical Docker daemon proxy changes were experimental and are not required setup steps.

## Replica-stop experiment

Start a two-minute stress plateau in one terminal. In another, stop a running replica about 100 seconds after k6 starts:

```powershell
$victim = docker compose ps -q api | Select-Object -First 1
docker stop $victim
```

After the test, restore the original replica count and refresh NGINX:

```powershell
docker compose up -d --scale api=3 api
docker compose restart nginx
```

Record stop timing and absolute failure counts. The historical test passed thresholds while losing one request. The old automated helper was removed because it assumed container names, overwrote evidence, and did not reliably propagate k6 failures.

## Capture comparison context

Save the commit (`git rev-parse HEAD`), working-tree status, Node/k6/Docker versions, resolved Compose configuration, image digests, replica count, CPU/RAM, Docker VM limits, row count, cache preparation, and full command. Save fresh logs and optionally k6's `--summary-export` JSON. Remove credentials from published configuration captures.

Inspect connections during load:

```powershell
docker compose exec -T -e PGPASSWORD=api pgbouncer psql -h 127.0.0.1 -p 6432 -U api -d pgbouncer -c "SHOW POOLS;"
docker compose exec -T postgres psql -U api -d api_scaling -c "SELECT count(*) FROM pg_stat_activity;"
```

Zero drops means k6 scheduled the workload. Drops can result from generator limits, network delay, or slow responses; a summary alone cannot identify the responsible component.
