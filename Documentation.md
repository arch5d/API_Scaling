# Implementation reference

This document describes the checked-in application. Setup is in the [README](README.md); experiment commands and evidence are in [RUNBOOK.md](benchmarks/RUNBOOK.md) and [PROGRESS.md](benchmarks/PROGRESS.md).

## Data and request paths

`src/server.js` connects Redis, builds the application, and listens. `src/app.js` registers routes and creates a PostgreSQL pool unless one is injected. Compose routes requests through NGINX to API replicas, then through PgBouncer to PostgreSQL. Redis stores full single-article responses; list queries always reach PostgreSQL.

`db/schema.sql` defines one `articles` table:

| Column       | Type         | Constraint                               |
| ------------ | ------------ | ---------------------------------------- |
| `id`         | BIGSERIAL    | Primary key                              |
| `title`      | VARCHAR(200) | Required                                 |
| `slug`       | VARCHAR(220) | Required, unique                         |
| `body`       | TEXT         | Required                                 |
| `author_id`  | BIGINT       | Nullable; no author table or foreign key |
| `created_at` | TIMESTAMPTZ  | Defaults to `now()`                      |
| `updated_at` | TIMESTAMPTZ  | Updated by PUT                           |

Indexes cover the primary key, unique slug, `(created_at DESC, id DESC)` ordering, and `author_id`. No endpoint currently uses the author index. Initialization scripts run only on an empty PostgreSQL volume; there is no migration runner. The seed inserts 100,000 small synthetic articles and runs `ANALYZE`.

## API contract

POST and PUT require `title`, `slug`, and `body`. Title is trimmed and must contain 1–200 characters. Slug is trimmed, contains 1–220 characters, and matches `^[a-z0-9]+(?:-[a-z0-9]+)*$`. Body must be a nonempty string. `authorId` accepts a positive integer, null, or omission. Omission on PUT clears the author. Validation strips unknown body fields.

IDs must parse as positive integers. Pagination accepts integer `limit` values from 1 to 100 (default 20), and nonnegative `offset` (default 0). SQL uses bound parameters. Large offsets remain potentially expensive.

Lists return `{ data, limit, offset }`, ordered by creation time and ID descending, without article bodies. Individual articles expose `id`, `title`, `slug`, `body`, `authorId`, `createdAt`, and `updatedAt`. PostgreSQL BIGINT values normally arrive as JSON strings through `pg`; timestamps serialize as ISO strings.

| Status | Meaning                                       |
| ------ | --------------------------------------------- |
| 200    | Read or update succeeded                      |
| 201    | Created                                       |
| 204    | Deleted; empty body                           |
| 304    | Exact matching `If-None-Match`; empty body    |
| 400    | Invalid input or ID                           |
| 404    | Article or route missing                      |
| 409    | Duplicate slug                                |
| 500    | Unexpected failure, including database errors |

Errors use Fastify's error response format. There are no authentication or ownership checks.

## Cache semantics

Reads look up `article:<id>`. A hit is parsed from JSON; a miss loads PostgreSQL and caches the result for 600 seconds. Missing articles are not cached. `X-Cache: HIT` means the initial lookup succeeded. `MISS` includes requests that waited for another process to fill the cache. The header is absent when caching is unavailable.

Concurrent misses within one process share a promise. Across processes, a fill attempts `SET NX PX` on `article:<id>:fill-lock` with a 5-second lease. Other processes poll every 10 ms for up to 2 seconds before querying PostgreSQL themselves. Lock release checks ownership with Lua. This reduces duplicate reads but does not guarantee one query across replicas, renew leases, or serialize writes.

PUT and DELETE invalidate Redis after changing PostgreSQL. A read started before a write can repopulate an old value after invalidation. Failed invalidation can leave stale data available to other replicas until expiry. These are eventual-consistency limitations.

A cache-operation error disables caching for that API process until restart. `/health` reports this local flag, not an active Redis probe. The Redis client's default reconnect policy can delay startup while Redis is unavailable. Outage recovery has not been validated by the retained benchmarks.

Successful individual reads emit:

```http
Cache-Control: public, max-age=60, stale-while-revalidate=30
ETag: "<id>-<ISO updatedAt>"
```

The handler compares `If-None-Match` with the exact emitted ETag; it does not support wildcard or multiple-tag matching. Redis invalidation cannot purge browser or intermediary caches. Conditional requests still perform a cache/database lookup before returning 304. The load test does not send conditional headers or simulate browser caching.

## Connections and proxy

Each API pool allows `DB_POOL_MAX` connections (default 10), with a 30-second idle timeout and 2-second connection timeout. Eight replicas can request up to 80 PgBouncer client connections; this is an upper bound, not observed usage.

PgBouncer allows 1,000 client connections, with default server pool size 20, minimum 5, and 5 reserve connections after a 3-second wait. Pool sizes apply per database/user pair: 20 is not an absolute global server-connection cap. Compose uses plain authentication with local development credentials on its internal network.

NGINX resolves API addresses when loading its configuration. Reload or restart NGINX after changing replica count or replacing API containers. Its connection timeout is 2 seconds and read/write timeouts are 30 seconds. This is not active health-checking service discovery.

## Configuration

| Variable        | Default                  | Purpose                                                              |
| --------------- | ------------------------ | -------------------------------------------------------------------- |
| `DATABASE_URL`  | No application default   | PostgreSQL or PgBouncer URL                                          |
| `REDIS_URL`     | `redis://localhost:6379` | Redis URL                                                            |
| `CACHE_ENABLED` | `true`                   | Set exactly `false` to skip Redis connection and use PostgreSQL only |
| `PORT`          | `3000`                   | Listening port                                                       |
| `HOST`          | `0.0.0.0`                | Listening interface                                                  |
| `DB_POOL_MAX`   | `10`                     | Per-process database pool limit                                      |
| `LOG_LEVEL`     | `warn`                   | Fastify logger level                                                 |

Compose sets service environment values explicitly. Editing `.env` alone does not override those values. `.env.example` supports a locally launched Node process.

## Metrics, health, and shutdown

`/health` executes `SELECT 1` and returns local cache state, PID, and hostname. Database exceptions return 500. It probes only the replica receiving the request.

Each replica exposes `http_requests_total`, `http_request_duration_seconds`, and default process metrics. Labels are method, route template, and status code; unmatched routes use a fixed label. Histogram buckets span 5 ms to 2 seconds. Scraping `/metrics` through NGINX samples different processes; scrape replicas separately to build meaningful aggregate time series. Prometheus and Grafana are not included.

SIGINT and SIGTERM close Fastify, attempt to quit an available cache client, and close the database pool. There is no forced-drain deadline. This is not a validated production failover system.

## Verification boundaries

The unit suite covers routes, validation, SQL parameters, cache hits/invalidation, cache failure fallback, ETags, metric labels, and local miss coalescing with dependency doubles. It does not test real Redis lock expiry, distributed invalidation races, reconnect behavior, or full database integration.

Historical load tests used small bodies and a strongly skewed read distribution. CPU model, VM allocation, image digests, and source revisions were not captured for each run. Publication-cleanup changes have not been re-benchmarked. Present the results as historical experiments, not guarantees for this checkout or other hardware.
