# Shareable visuals

All images are 1600 × 900. They use repository code and retained benchmark evidence, with no invented dashboard or measurements.

| Image                           | Exact content                                                                                                                                                                                                          | Downloads                                                                  |
| ------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| Controlled latency              | p95 and p99 ranges for all five configurations, showing both repetitions on logarithmic axes. Values are derived from the completed November 24 matrix.                                                                | [PNG](images/controlled-latency.png), [SVG](images/controlled-latency.svg) |
| Controlled summary              | Four comparison cards with observed p95 ranges, threshold passes, absolute HTTP failures and dropped iterations. The README contains the full five-configuration table.                                                | [PNG](images/controlled-summary.png), [SVG](images/controlled-summary.svg) |
| Architecture                    | Client/k6 → NGINX → Fastify replicas; Fastify → Redis and PgBouncer → PostgreSQL. Note cache TTL, DB pool size, list/write behavior and shared host.                                                                   | [PNG](images/architecture.png), [SVG](images/architecture.svg)             |
| Historical cache chart (Nov 19) | One stacked bar: 522,009 hits and 2,848 misses, 99.46% hits. Denominator is recorded HIT/MISS responses, not all requests.                                                                                             | [PNG](images/cache-hit-rate.png), [SVG](images/cache-hit-rate.svg)         |
| Historical summary (Nov 19)     | Eight-replica accepted run: 921.10 HTTP RPS whole-run average, 1,000 iterations/s configured plateau, 11.70 ms p95, 27.95 ms p99, 0/663,132 failed requests, zero drops. State network path and missing VM allocation. | [PNG](images/benchmark-summary.png), [SVG](images/benchmark-summary.svg)   |

Summary cards are formatted evidence images, not screenshots. Current data: [controlled matrix](../benchmarks/CURRENT.md). Historical source: [original k6 log](../benchmarks/stress-published-linuxvm-10m.log). No GIF is needed for a static summary.

## Regenerate exactly

From the repository root on Windows, using Python 3 and PowerShell:

```powershell
python docs/images/generate.py
powershell -NoProfile -ExecutionPolicy Bypass -File docs/images/export-png.ps1
python benchmarks/summarize.py benchmarks/results/2026-11-24-matrix
python docs/images/generate-comparison.py
powershell -NoProfile -ExecutionPolicy Bypass -File docs/images/export-png.ps1 -Manifest drawing-current.json
npx.cmd prettier --write docs/images/drawing.json docs/images/drawing-current.json
```

Python writes the SVGs and shared drawing manifest; PowerShell uses System.Drawing to export PNGs. No image-generation service or added Python packages are required. Current comparison values are derived from all ten retained summaries. Historical cache counts are parsed from the original log; other historical labels describe that specific run. Update provenance before reusing these images for another run.

## If you want an actual terminal screenshot

Open `benchmarks/stress-published-linuxvm-10m.log` in a terminal or editor. Capture the final THRESHOLDS and TOTAL RESULTS blocks, including cache counters, HTTP request counts, latency, dropped iterations and iterations. Keep the filename visible, use a dark background and readable monospace text, and exclude unrelated windows or credentials. Label it “Saved k6 output — 19 November 2026”; do not present it as a fresh run. The generated card already provides a more compact alternative for sharing.

## Repository publication

The repository About description is "Fastify API scaling experiments with Redis caching, PgBouncer pooling, NGINX replicas, and reproducible k6 load tests." Topics: `fastify`, `redis`, `pgbouncer`, `nginx`, `k6`, `load-testing`, `scalability`, `docker`.

Use the architecture PNG for the project overview and the controlled-latency PNG for the results post. Keep the date, workload, shared-host limitation and failure counts visible when sharing. The historical images describe a different experiment and should not be presented as the November 24 matrix.
