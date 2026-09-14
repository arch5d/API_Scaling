import { createClient } from 'redis';
import { buildApp } from './app.js';

const port = Number(process.env.PORT ?? 3000);

const cache = createClient({ url: process.env.REDIS_URL ?? 'redis://localhost:6379' });
let app;
cache.on('error', (error) => app?.log?.warn({ error }, 'redis unavailable'));

let cacheEnabled = false;
try {
  await cache.connect();
  cacheEnabled = true;
} catch (error) {
  app.log?.warn?.({ error }, 'redis unavailable; using postgres only');
}

app = await buildApp({ cache: cacheEnabled ? cache : null });
if (cacheEnabled) {
  app.log.info('redis cache enabled');
}

const shutdown = async (signal) => {
  app.log.info({ signal }, 'shutting down');
  await app.close();
  if (app.cacheAvailable()) await app.cache.quit();
  await app.pool.end();
  process.exit(0);
};
process.once('SIGINT', shutdown);
process.once('SIGTERM', shutdown);

await app.listen({ port, host: process.env.HOST ?? '0.0.0.0' });
