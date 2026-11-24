# Shareable visuals

All three images are 1600 × 900. They use repository code and retained benchmark evidence, with no invented dashboard or measurements.

| Image           | Exact content                                                                                                                                                                                                          | Downloads                                                                |
| --------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| Architecture    | Client/k6 → NGINX → Fastify replicas; Fastify → Redis and PgBouncer → PostgreSQL. Note cache TTL, DB pool size, list/write behavior and shared host.                                                                   | [PNG](images/architecture.png), [SVG](images/architecture.svg)           |
| Cache hit chart | One stacked bar: 522,009 hits and 2,848 misses, 99.46% hits. Denominator is recorded HIT/MISS responses, not all requests.                                                                                             | [PNG](images/cache-hit-rate.png), [SVG](images/cache-hit-rate.svg)       |
| k6 summary card | Eight-replica accepted run: 921.10 HTTP RPS whole-run average, 1,000 iterations/s configured plateau, 11.70 ms p95, 27.95 ms p99, 0/663,132 failed requests, zero drops. State network path and missing VM allocation. | [PNG](images/benchmark-summary.png), [SVG](images/benchmark-summary.svg) |

The summary card is a formatted evidence image, not a screenshot. Source: [original k6 log](../benchmarks/stress-published-linuxvm-10m.log). No GIF is needed for a static summary.

## Regenerate exactly

From the repository root on Windows, using Python 3 and PowerShell:

```powershell
python docs/images/generate.py
powershell -NoProfile -ExecutionPolicy Bypass -File docs/images/export-png.ps1
npx.cmd prettier --write docs/images/drawing.json
```

Python writes the SVGs and shared drawing manifest; PowerShell uses System.Drawing to export PNGs. No image-generation service or added Python packages are required. Cache counts are parsed from the source log; other labels describe that specific historical run. Update provenance before reusing these images for another run.

## If you want an actual terminal screenshot

Open `benchmarks/stress-published-linuxvm-10m.log` in a terminal or editor. Capture the final THRESHOLDS and TOTAL RESULTS blocks, including cache counters, HTTP request counts, latency, dropped iterations and iterations. Keep the filename visible, use a dark background and readable monospace text, and exclude unrelated windows or credentials. Label it “Saved k6 output — 19 November 2026”; do not present it as a fresh run. The generated card already provides a more compact alternative for sharing.

## Repository About and optional release

The GitHub connector has no repository-settings or release-write operation, and the local GitHub CLI was not authenticated when these assets were prepared. After signing in with `gh auth login`, apply the requested metadata:

```powershell
gh repo edit arch5d/API_Scaling --description "Fastify API scaling experiments with Redis caching, PgBouncer pooling, NGINX replicas, and reproducible k6 load tests." --add-topic fastify,redis,pgbouncer,nginx,k6,load-testing,scalability,docker
```

Optional release: first review, commit and push the documentation and images. Then tag that reviewed commit explicitly (replace `REVIEWED_COMMIT_SHA` with its SHA):

```powershell
git tag -a v1.0.0 REVIEWED_COMMIT_SHA -m "v1.0.0: documented API scaling experiments"
git push origin v1.0.0
gh release create v1.0.0 --repo arch5d/API_Scaling --verify-tag --title "v1.0.0 — API scaling experiments" --notes "Fastify, Redis, PgBouncer and NGINX experiment stack, reproducible k6 workload, retained benchmark evidence, and shareable architecture and result visuals. Benchmark limitations and missing controlled baselines are documented in the README."
```

No release was created as part of preparing these files.
