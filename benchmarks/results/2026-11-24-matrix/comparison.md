| Run | HTTP RPS | p95 (ms) | p99 (ms) | Failed / total | Dropped | Thresholds |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| [1-direct-no-cache-r1](1-direct-no-cache-r1/k6.log) | 733.51 | 70.42 | 719.66 | 1,117 / 176,023 | 2,091 | Fail |
| [1-direct-no-cache-r2](1-direct-no-cache-r2/k6.log) | 742.30 | 50.71 | 112.04 | 0 / 178,130 | 0 | Pass |
| [1-direct-redis-r1](1-direct-redis-r1/k6.log) | 740.57 | 12.34 | 93.59 | 0 / 177,719 | 458 | Fail |
| [1-direct-redis-r2](1-direct-redis-r2/k6.log) | 742.50 | 37.92 | 102.61 | 0 / 178,179 | 7 | Fail |
| [1-pool-redis-r1](1-pool-redis-r1/k6.log) | 742.70 | 5.11 | 8.91 | 0 / 178,223 | 0 | Pass |
| [1-pool-redis-r2](1-pool-redis-r2/k6.log) | 742.95 | 13.63 | 42.06 | 0 / 178,286 | 0 | Pass |
| [3-pool-redis-r1](3-pool-redis-r1/k6.log) | 742.22 | 5.20 | 9.63 | 0 / 178,107 | 0 | Pass |
| [3-pool-redis-r2](3-pool-redis-r2/k6.log) | 742.70 | 5.94 | 11.20 | 0 / 178,223 | 0 | Pass |
| [8-pool-redis-r1](8-pool-redis-r1/k6.log) | 742.62 | 13.71 | 56.75 | 0 / 178,204 | 0 | Pass |
| [8-pool-redis-r2](8-pool-redis-r2/k6.log) | 742.45 | 11.85 | 51.63 | 0 / 178,157 | 0 | Pass |
