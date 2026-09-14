import http from 'k6/http';
import { check } from 'k6';
import { Counter } from 'k6/metrics';

const baseUrl = __ENV.BASE_URL || 'http://localhost:3000';
const smoke = __ENV.SMOKE === 'true';
const stress = __ENV.STRESS === 'true';
const realisticReads = __ENV.ACCESS_PATTERN === 'realistic';
const cacheHits = new Counter('article_cache_hits');
const cacheMisses = new Counter('article_cache_misses');

export const options = {
  scenarios: {
    baseline: {
      executor: 'ramping-arrival-rate',
      startRate: 10,
      timeUnit: '1s',
        preAllocatedVUs: stress ? 300 : 50,
        maxVUs: stress ? 1000 : 300,
      stages: stress
        ? [
            { target: 250, duration: '30s' },
            { target: 1000, duration: '10m' },
            { target: 0, duration: '30s' }
          ]
        : smoke
        ? [
            { target: 30, duration: '10s' },
            { target: 30, duration: '20s' },
            { target: 0, duration: '5s' }
          ]
        : [
            { target: 100, duration: '2m' },
            { target: 100, duration: '10m' },
            { target: 0, duration: '1m' }
          ]
    }
  },
  thresholds: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<250', 'p(99)<500'],
    dropped_iterations: ['count==0']
  }
};

export default function () {
  const roll = Math.random();
  let response;
  if (roll < 0.80) {
    const articleId = realisticReads
      ? Math.min(100000, Math.floor(1 / Math.pow(1 - Math.random(), 1 / 0.8)))
      : Math.floor(Math.random() * 100000) + 1;
    response = http.get(`${baseUrl}/articles/${articleId}`);
  } else if (roll < 0.95) {
    response = http.get(`${baseUrl}/articles?limit=20&offset=${Math.floor(Math.random() * 1000)}`);
  } else {
    const article = JSON.stringify({
      title: `Load test article ${__VU}-${__ITER}`,
      slug: `load-test-${__VU}-${__ITER}-${Date.now()}`,
      body: 'Load test content'
    });
    const headers = { headers: { 'Content-Type': 'application/json' } };
    const writeType = Math.random();
    if (writeType < 0.6) {
      response = http.post(`${baseUrl}/articles`, article, headers);
    } else if (writeType < 0.8) {
      response = http.put(`${baseUrl}/articles/${Math.floor(Math.random() * 100000) + 1}`, article, headers);
    } else {
      const createResponse = http.post(`${baseUrl}/articles`, article, headers);
      if (createResponse.status === 201) {
        response = http.del(`${baseUrl}/articles/${createResponse.json('id')}`);
      } else {
        response = createResponse;
      }
    }
  }
  if (response.url.includes('/articles/') && response.headers['X-Cache'] === 'HIT') cacheHits.add(1);
  if (response.url.includes('/articles/') && response.headers['X-Cache'] === 'MISS') cacheMisses.add(1);
  check(response, { 'status is successful': (result) => result.status >= 200 && result.status < 400 });
}
