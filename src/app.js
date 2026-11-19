import Fastify from 'fastify';
import sensible from '@fastify/sensible';
import pg from 'pg';
import client from 'prom-client';
import os from 'node:os';
import { z } from 'zod';

const { Pool } = pg;
const { Counter, Histogram, Registry } = client;

const CACHE_CONTROL = 'public, max-age=60, stale-while-revalidate=30';
const FILL_LOCK_TTL_MS = 5000;
const WAIT_FOR_FILL_MS = 2000;
const RELEASE_LOCK_SCRIPT =
  "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) else return 0 end";

const articleInput = z.object({
  title: z.string().trim().min(1).max(200),
  slug: z
    .string()
    .trim()
    .min(1)
    .max(220)
    .regex(/^[a-z0-9]+(?:-[a-z0-9]+)*$/),
  body: z.string().min(1),
  authorId: z.number().int().positive().nullable().optional()
});
const pagination = z.object({
  limit: z.coerce.number().int().min(1).max(100).default(20),
  offset: z.coerce.number().int().min(0).default(0)
});

export async function buildApp({
  pool,
  cache = null,
  logger = { level: process.env.LOG_LEVEL ?? 'warn' }
} = {}) {
  if (!pool) {
    pool = new Pool({
      connectionString: process.env.DATABASE_URL,
      max: Number(process.env.DB_POOL_MAX ?? 10),
      idleTimeoutMillis: 30_000,
      connectionTimeoutMillis: 2_000
    });
  }

  const app = Fastify({ logger });
  await app.register(sensible);

  app.addHook('onListen', async () => {
    app.server.keepAliveTimeout = 60_000;
    app.server.headersTimeout = 61_000;
    app.server.requestTimeout = 65_000;
  });

  let cacheAvailable = cache != null;
  const fillsInFlight = new Map();

  const metricsRegistry = new Registry();
  client.collectDefaultMetrics({ register: metricsRegistry });
  const requestCount = new Counter({
    name: 'http_requests_total',
    help: 'Total HTTP requests handled by the API.',
    labelNames: ['method', 'route', 'status_code'],
    registers: [metricsRegistry]
  });
  const requestDuration = new Histogram({
    name: 'http_request_duration_seconds',
    help: 'HTTP request duration in seconds.',
    labelNames: ['method', 'route', 'status_code'],
    registers: [metricsRegistry],
    buckets: [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2]
  });

  app.addHook('onRequest', async (request) => {
    request.metricsStart = process.hrtime.bigint();
  });
  app.addHook('onResponse', async (request, reply) => {
    const route = request.routeOptions?.url ?? request.url.split('?')[0];
    const labels = { method: request.method, route, status_code: String(reply.statusCode) };
    requestCount.inc(labels);
    const elapsedSeconds = Number(process.hrtime.bigint() - request.metricsStart) / 1e9;
    requestDuration.observe(labels, elapsedSeconds);
  });

  const readCache = async (key) => {
    if (!cacheAvailable) return null;
    try {
      return await cache.get(key);
    } catch (error) {
      cacheAvailable = false;
      app.log.warn({ error }, 'redis read failed; using postgres');
      return null;
    }
  };

  const writeCache = async (key, value) => {
    if (!cacheAvailable) return;
    try {
      await cache.set(key, value, { EX: 600 });
    } catch (error) {
      cacheAvailable = false;
      app.log.warn({ error }, 'redis write failed; using postgres');
    }
  };

  const deleteCache = async (key) => {
    if (!cacheAvailable) return;
    try {
      await cache.del(key);
    } catch (error) {
      cacheAvailable = false;
      app.log.warn({ error }, 'redis delete failed; using postgres');
    }
  };

  const lockKey = (key) => `${key}:fill-lock`;

  const acquireFillLock = async (key, token) => {
    if (!cacheAvailable || !cache) return false;
    try {
      return (await cache.set(lockKey(key), token, { NX: true, PX: FILL_LOCK_TTL_MS })) === 'OK';
    } catch (error) {
      cacheAvailable = false;
      app.log.warn({ error }, 'redis lock failed; using postgres');
      return false;
    }
  };

  const releaseFillLock = async (key, token) => {
    if (!cacheAvailable || typeof cache?.eval !== 'function') return;
    try {
      await cache.eval(RELEASE_LOCK_SCRIPT, {
        keys: [lockKey(key)],
        arguments: [token]
      });
    } catch (error) {
      cacheAvailable = false;
      app.log.warn({ error }, 'redis unlock failed; using postgres');
    }
  };

  // Coalesce concurrent misses for the same key. The Redis fill lock also deduplicates
  // across replicas; local callers share a single Promise, remote callers wait for the cache.
  const loadArticle = async (key, fetchFromDatabase) => {
    const existing = fillsInFlight.get(key);
    if (existing) return existing;

    const task = (async () => {
      const token = `${os.hostname()}:${process.pid}:${Date.now()}:${Math.random()}`;
      const locked = await acquireFillLock(key, token);
      if (!locked && cacheAvailable) {
        const deadline = Date.now() + WAIT_FOR_FILL_MS;
        while (Date.now() < deadline) {
          await new Promise((resolve) => setTimeout(resolve, 10));
          const filled = await readCache(key);
          if (filled) return JSON.parse(filled);
        }
      }
      try {
        const article = await fetchFromDatabase();
        if (article) await writeCache(key, JSON.stringify(article));
        return article;
      } finally {
        if (locked) await releaseFillLock(key, token);
      }
    })();

    fillsInFlight.set(key, task);
    try {
      return await task;
    } finally {
      fillsInFlight.delete(key);
    }
  };

  const articleEtag = (article) => `"${article.id}-${article.updatedAt}"`;

  app.get('/', async (_request, reply) => {
    return reply.send({
      service: 'api-scaling-blog',
      status: 'ok',
      health: '/health',
      metrics: '/metrics',
      endpoints: {
        articles: '/articles',
        article: '/articles/:id'
      }
    });
  });

  app.get('/health', async (_request, reply) => {
    const result = await pool.query('SELECT 1 AS ok');
    return reply.send({
      status: result.rows[0].ok === 1 ? 'ok' : 'degraded',
      cache: cacheAvailable ? 'ready' : 'unavailable',
      pid: process.pid,
      hostname: os.hostname()
    });
  });

  app.get('/metrics', async (_request, reply) => {
    return reply.type(metricsRegistry.contentType).send(await metricsRegistry.metrics());
  });

  app.get('/articles', async (request) => {
    const { limit, offset } = pagination.parse(request.query);
    const result = await pool.query(
      `SELECT id, title, slug, author_id AS "authorId", created_at AS "createdAt", updated_at AS "updatedAt"
       FROM articles ORDER BY created_at DESC, id DESC LIMIT $1 OFFSET $2`,
      [limit, offset]
    );
    return { data: result.rows, limit, offset };
  });

  app.get('/articles/:id', async (request, reply) => {
    const id = Number(request.params.id);
    if (!Number.isInteger(id) || id < 1) return reply.badRequest('id must be a positive integer');

    const cacheKey = `article:${id}`;
    let article;
    let cacheStatus;
    const cached = await readCache(cacheKey);
    if (cached) {
      article = JSON.parse(cached);
      cacheStatus = 'HIT';
    } else {
      article = await loadArticle(cacheKey, async () => {
        const result = await pool.query(
          `SELECT id, title, slug, body, author_id AS "authorId", created_at AS "createdAt", updated_at AS "updatedAt"
           FROM articles WHERE id = $1`,
          [id]
        );
        return result.rowCount === 0 ? null : result.rows[0];
      });
      if (cacheAvailable) cacheStatus = 'MISS';
    }
    if (!article) return reply.notFound('article not found');

    const etag = articleEtag(article);
    reply.header('Cache-Control', CACHE_CONTROL).header('ETag', etag);
    if (cacheStatus) reply.header('X-Cache', cacheStatus);
    if (request.headers['if-none-match'] === etag) return reply.code(304).send();
    return article;
  });

  app.post('/articles', async (request, reply) => {
    const input = articleInput.parse(request.body);
    const result = await pool.query(
      `INSERT INTO articles (title, slug, body, author_id) VALUES ($1, $2, $3, $4)
       RETURNING id, title, slug, body, author_id AS "authorId", created_at AS "createdAt", updated_at AS "updatedAt"`,
      [input.title, input.slug, input.body, input.authorId ?? null]
    );
    return reply.code(201).send(result.rows[0]);
  });

  app.put('/articles/:id', async (request, reply) => {
    const id = Number(request.params.id);
    if (!Number.isInteger(id) || id < 1) return reply.badRequest('id must be a positive integer');
    const input = articleInput.parse(request.body);
    const result = await pool.query(
      `UPDATE articles SET title = $1, slug = $2, body = $3, author_id = $4, updated_at = now()
       WHERE id = $5
       RETURNING id, title, slug, body, author_id AS "authorId", created_at AS "createdAt", updated_at AS "updatedAt"`,
      [input.title, input.slug, input.body, input.authorId ?? null, id]
    );
    if (result.rowCount === 0) return reply.notFound('article not found');
    await deleteCache(`article:${id}`);
    return result.rows[0];
  });

  app.delete('/articles/:id', async (request, reply) => {
    const id = Number(request.params.id);
    if (!Number.isInteger(id) || id < 1) return reply.badRequest('id must be a positive integer');
    const result = await pool.query('DELETE FROM articles WHERE id = $1', [id]);
    if (result.rowCount === 0) return reply.notFound('article not found');
    await deleteCache(`article:${id}`);
    return reply.code(204).send();
  });

  app.setErrorHandler((error, _request, reply) => {
    if (error.name === 'ZodError') return reply.badRequest(error.issues);
    if (error.code === '23505') return reply.conflict('slug already exists');
    if (error.statusCode >= 400 && error.statusCode < 500) return reply.send(error);
    app.log.error(error);
    return reply.internalServerError();
  });

  app.decorate('pool', pool);
  app.decorate('cache', cache);
  app.decorate('cacheAvailable', () => cacheAvailable);

  return app;
}
