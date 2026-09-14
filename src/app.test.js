import { describe, it, expect, vi } from 'vitest';
import { buildApp } from './app.js';

const ARTICLE = {
  id: 1,
  title: 'Hello World',
  slug: 'hello-world',
  body: 'Body text',
  authorId: null,
  createdAt: '2026-01-01T00:00:00.000Z',
  updatedAt: '2026-01-01T00:00:00.000Z'
};

const NEW_ARTICLE = {
  ...ARTICLE,
  id: 2,
  title: 'New Article',
  slug: 'new-article'
};

function createPool(handler) {
  const calls = [];
  const pool = {
    calls,
    async query(text, params) {
      calls.push({ text, params });
      if (handler) return handler(text, params);
      return { rows: [], rowCount: 0 };
    }
  };
  return { pool, calls };
}

function createCache(initial = {}) {
  const store = new Map(Object.entries(initial));
  return {
    get: vi.fn(async (key) => (store.has(key) ? store.get(key) : null)),
    set: vi.fn(async (key, value, _options) => {
      store.set(key, value);
      return 'OK';
    }),
    del: vi.fn(async (key) => {
      const had = store.delete(key);
      return had ? 1 : 0;
    })
  };
}

describe('GET /', () => {
  it('returns service information', async () => {
    const app = await buildApp({ pool: createPool().pool });
    const res = await app.inject({ method: 'GET', url: '/' });
    expect(res.statusCode).toBe(200);
    const body = res.json();
    expect(body.service).toBe('api-scaling-blog');
    expect(body.endpoints.articles).toBe('/articles');
  });
});

describe('GET /health', () => {
  it('reports ok when the database responds', async () => {
    const { pool } = createPool(() => ({ rows: [{ ok: 1 }] }));
    const app = await buildApp({ pool });
    const res = await app.inject({ method: 'GET', url: '/health' });
    expect(res.statusCode).toBe(200);
    expect(res.json().status).toBe('ok');
  });

  it('reports degraded when the database does not respond', async () => {
    const { pool } = createPool(() => ({ rows: [{ ok: 0 }] }));
    const app = await buildApp({ pool });
    const res = await app.inject({ method: 'GET', url: '/health' });
    expect(res.json().status).toBe('degraded');
  });

  it('reports cache readiness', async () => {
    const cache = createCache();
    const { pool } = createPool(() => ({ rows: [{ ok: 1 }] }));
    const app = await buildApp({ pool, cache });
    const res = await app.inject({ method: 'GET', url: '/health' });
    expect(res.json().cache).toBe('ready');
  });
});

describe('GET /metrics', () => {
  it('exposes Prometheus text metrics', async () => {
    const app = await buildApp({ pool: createPool().pool });
    const res = await app.inject({ method: 'GET', url: '/metrics' });
    expect(res.statusCode).toBe(200);
    expect(res.body).toContain('http_requests_total');
    expect(res.body).toContain('http_request_duration_seconds');
  });
});

describe('GET /articles', () => {
  it('lists articles with provided pagination', async () => {
    const { pool, calls } = createPool(() => ({ rows: [ARTICLE], rowCount: 1 }));
    const app = await buildApp({ pool });
    const res = await app.inject({ method: 'GET', url: '/articles?limit=5&offset=10' });
    expect(res.statusCode).toBe(200);
    expect(res.json()).toEqual({ data: [ARTICLE], limit: 5, offset: 10 });
    expect(calls[0].params).toEqual([5, 10]);
  });

  it('applies default pagination', async () => {
    const { pool, calls } = createPool(() => ({ rows: [], rowCount: 0 }));
    const app = await buildApp({ pool });
    await app.inject({ method: 'GET', url: '/articles' });
    expect(calls[0].params).toEqual([20, 0]);
  });

  it('rejects an invalid limit', async () => {
    const app = await buildApp({ pool: createPool().pool });
    const res = await app.inject({ method: 'GET', url: '/articles?limit=0' });
    expect(res.statusCode).toBe(400);
  });

  it('rejects an invalid offset', async () => {
    const app = await buildApp({ pool: createPool().pool });
    const res = await app.inject({ method: 'GET', url: '/articles?offset=-1' });
    expect(res.statusCode).toBe(400);
  });
});

describe('GET /articles/:id', () => {
  it('serves a cache hit', async () => {
    const cache = createCache({ 'article:1': JSON.stringify(ARTICLE) });
    const app = await buildApp({ pool: createPool().pool, cache });
    const res = await app.inject({ method: 'GET', url: '/articles/1' });
    expect(res.statusCode).toBe(200);
    expect(res.headers['x-cache']).toBe('HIT');
    expect(res.json()).toEqual(ARTICLE);
  });

  it('misses the cache, reads the database, and populates the cache', async () => {
    const cache = createCache();
    const { pool } = createPool(() => ({ rows: [ARTICLE], rowCount: 1 }));
    const app = await buildApp({ pool, cache });
    const res = await app.inject({ method: 'GET', url: '/articles/1' });
    expect(res.statusCode).toBe(200);
    expect(res.headers['x-cache']).toBe('MISS');
    expect(cache.set).toHaveBeenCalledWith('article:1', JSON.stringify(ARTICLE), { EX: 600 });
  });

  it('returns 404 for a missing article', async () => {
    const app = await buildApp({ pool: createPool().pool });
    const res = await app.inject({ method: 'GET', url: '/articles/99999' });
    expect(res.statusCode).toBe(404);
  });

  it('rejects a non-positive id', async () => {
    const app = await buildApp({ pool: createPool().pool });
    for (const url of ['/articles/abc', '/articles/0', '/articles/-5', '/articles/1.5']) {
      const res = await app.inject({ method: 'GET', url });
      expect(res.statusCode).toBe(400);
    }
  });

  it('falls back to the database when the cache fails', async () => {
    const cache = {
      get: vi.fn(async () => {
        throw new Error('redis down');
      })
    };
    const { pool } = createPool(() => ({ rows: [ARTICLE], rowCount: 1 }));
    const app = await buildApp({ pool, cache });
    const res = await app.inject({ method: 'GET', url: '/articles/1' });
    expect(res.statusCode).toBe(200);
    expect(res.json()).toEqual(ARTICLE);
    expect(res.headers['x-cache']).toBeUndefined();
  });
});

describe('POST /articles', () => {
  it('creates an article', async () => {
    const { pool } = createPool(() => ({ rows: [NEW_ARTICLE], rowCount: 1 }));
    const app = await buildApp({ pool });
    const res = await app.inject({
      method: 'POST',
      url: '/articles',
      payload: { title: 'New Article', slug: 'new-article', body: 'Body', authorId: 5 }
    });
    expect(res.statusCode).toBe(201);
    expect(res.json()).toEqual(NEW_ARTICLE);
  });

  it('rejects an invalid payload', async () => {
    const app = await buildApp({ pool: createPool().pool });
    const res = await app.inject({
      method: 'POST',
      url: '/articles',
      payload: { title: '', slug: 'Bad Slug!', body: '' }
    });
    expect(res.statusCode).toBe(400);
  });

  it('returns 409 on a unique slug conflict', async () => {
    const { pool } = createPool(() => {
      const error = new Error('duplicate key value violates unique constraint');
      error.code = '23505';
      throw error;
    });
    const app = await buildApp({ pool });
    const res = await app.inject({
      method: 'POST',
      url: '/articles',
      payload: { title: 'New', slug: 'new-article', body: 'Body' }
    });
    expect(res.statusCode).toBe(409);
  });
});

describe('PUT /articles/:id', () => {
  it('updates an article and invalidates the cache', async () => {
    const cache = createCache({ 'article:1': JSON.stringify(ARTICLE) });
    const { pool } = createPool(() => ({ rows: [NEW_ARTICLE], rowCount: 1 }));
    const app = await buildApp({ pool, cache });
    const res = await app.inject({
      method: 'PUT',
      url: '/articles/1',
      payload: { title: 'New Article', slug: 'new-article', body: 'Body' }
    });
    expect(res.statusCode).toBe(200);
    expect(res.json()).toEqual(NEW_ARTICLE);
    expect(cache.del).toHaveBeenCalledWith('article:1');
  });

  it('returns 404 when the article does not exist', async () => {
    const app = await buildApp({ pool: createPool().pool });
    const res = await app.inject({
      method: 'PUT',
      url: '/articles/99999',
      payload: { title: 'New Article', slug: 'new-article', body: 'Body' }
    });
    expect(res.statusCode).toBe(404);
  });

  it('rejects a non-positive id', async () => {
    const app = await buildApp({ pool: createPool().pool });
    const payload = { title: 'New Article', slug: 'new-article', body: 'Body' };
    const res = await app.inject({ method: 'PUT', url: '/articles/abc', payload });
    expect(res.statusCode).toBe(400);
  });
});

describe('DELETE /articles/:id', () => {
  it('deletes an article and invalidates the cache', async () => {
    const cache = createCache({ 'article:1': JSON.stringify(ARTICLE) });
    const { pool } = createPool(() => ({ rows: [], rowCount: 1 }));
    const app = await buildApp({ pool, cache });
    const res = await app.inject({ method: 'DELETE', url: '/articles/1' });
    expect(res.statusCode).toBe(204);
    expect(cache.del).toHaveBeenCalledWith('article:1');
  });

  it('returns 404 when the article does not exist', async () => {
    const app = await buildApp({ pool: createPool().pool });
    const res = await app.inject({ method: 'DELETE', url: '/articles/99999' });
    expect(res.statusCode).toBe(404);
  });

  it('rejects a non-positive id', async () => {
    const app = await buildApp({ pool: createPool().pool });
    const res = await app.inject({ method: 'DELETE', url: '/articles/0' });
    expect(res.statusCode).toBe(400);
  });
});
