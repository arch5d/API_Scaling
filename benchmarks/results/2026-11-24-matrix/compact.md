| Config | HTTP RPS range | p95 range (ms) | p99 range (ms) | Failed / total | Drops | Passed |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 replica, no cache; direct DB | 733.51–742.30 | 50.71–70.42 | 112.04–719.66 | 1,117 / 354,153 | 2,091 | 1/2 |
| 1 replica + Redis; direct DB | 740.57–742.50 | 12.34–37.92 | 93.59–102.61 | 0 / 355,898 | 465 | 0/2 |
| 1 replica + Redis + PgBouncer | 742.70–742.95 | 5.11–13.63 | 8.91–42.06 | 0 / 356,509 | 0 | 2/2 |
| 3 replicas + Redis + PgBouncer | 742.22–742.70 | 5.20–5.94 | 9.63–11.20 | 0 / 356,330 | 0 | 2/2 |
| 8 replicas + Redis + PgBouncer | 742.45–742.62 | 11.85–13.71 | 51.63–56.75 | 0 / 356,361 | 0 | 2/2 |
