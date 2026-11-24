"""Generate evidence-based SVGs and a drawing manifest for PNG export (stdlib only)."""
import json
import re
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
raw = (ROOT / 'benchmarks/stress-published-linuxvm-10m.log').read_bytes()
log = raw.decode('utf-16' if raw.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig')
def count(name):
    return int(re.search(rf'{name}\.+:\s+(\d+)', log)[1])
hits, misses = count('article_cache_hits'), count('article_cache_misses')
rate = hits / (hits + misses) * 100
pages = {}
def page(name, title, subtitle):
    shapes = []
    pages[name] = shapes
    shapes.append(dict(kind='rect', x=0, y=0, w=1600, h=900, color='#101827'))
    text(shapes, 70, 55, title, 48, '#f5f8ff')
    text(shapes, 70, 125, subtitle, 25, '#aebed5')
    return shapes
def text(s, x, y, value, size=28, color='#f5f8ff'):
    s.append(dict(kind='text', x=x, y=y, value=value, size=size, color=color))
def box(s, x, y, w, h, title, detail):
    s.append(dict(kind='rect', x=x, y=y, w=w, h=h, color='#21324b'))
    text(s, x+24, y+25, title, 32)
    text(s, x+24, y+78, detail, 23, '#aebed5')
def arrow(s, x, y, xx, yy):
    s.append(dict(kind='line', x=x, y=y, xx=xx, yy=yy, color='#65ddc0'))
    # All diagram arrows are horizontal or vertical.
    if xx > x:
        arrowheads = [(xx-14, yy-9), (xx-14, yy+9)]
    else:
        arrowheads = [(xx-9, yy-14), (xx+9, yy-14)]
    for ax, ay in arrowheads:
        s.append(dict(kind='line', x=ax, y=ay, xx=xx, yy=yy, color='#65ddc0'))

s = page('architecture', 'API scaling: the request path', 'Local Docker Desktop stack | configurable Fastify replicas')
box(s, 70, 245, 280, 140, 'Client / k6', 'Mixed CRUD workload')
box(s, 430, 245, 280, 140, 'NGINX', 'localhost:3000')
box(s, 790, 245, 350, 140, 'Fastify replicas', 'DB pool: 10 / replica')
arrow(s, 350, 315, 430, 315)
arrow(s, 710, 315, 790, 315)
box(s, 1220, 245, 310, 140, 'Redis', 'Article cache: 10 min')
arrow(s, 1140, 315, 1220, 315)
box(s, 790, 515, 350, 140, 'PgBouncer', 'Transaction pooling')
arrow(s, 965, 385, 965, 515)
box(s, 1220, 515, 310, 140, 'PostgreSQL', 'Source of truth')
arrow(s, 1140, 585, 1220, 585)
text(s, 70, 485, 'Single reads: Redis first;', 27)
text(s, 70, 530, 'misses reach PostgreSQL.', 27)
text(s, 70, 595, 'Lists and writes: database.', 27)
text(s, 70, 640, 'Writes invalidate cached articles.', 27)
text(s, 70, 775, 'k6 shares host resources with the system under test.', 27, '#65ddc0')
text(s, 70, 825, 'Single NGINX, Redis and PostgreSQL instances; no high-availability claim.', 24, '#aebed5')

s = page('cache-hit-rate', 'What the recorded cache counters show', '8 replicas | published port from a Linux bridge inside Docker Desktop')
text(s, 70, 230, f'{rate:.2f}% cache hits', 80, '#65ddc0')
text(s, 70, 350, f'{hits:,} HIT / {misses:,} MISS responses', 36)
s.append(dict(kind='rect', x=70, y=440, w=1460, h=90, color='#f5ae70'))
s.append(dict(kind='rect', x=70, y=440, w=1460*rate/100, h=90, color='#65ddc0'))
text(s, 70, 565, f'HIT {rate:.2f}%', 30, '#65ddc0')
text(s, 1130, 565, f'MISS {100-rate:.2f}%', 30, '#f5ae70')
text(s, 70, 665, 'Denominator: responses counted with X-Cache HIT or MISS.', 28)
text(s, 70, 715, 'Not all HTTP requests. Synthetic skewed reads; whole run including ramps.', 26, '#aebed5')
text(s, 70, 765, 'This measures cache usage, not the speedup caused by Redis.', 26, '#aebed5')
text(s, 70, 830, 'Source: benchmarks/stress-published-linuxvm-10m.log | 19 Nov 2026', 23, '#aebed5')

s = page('benchmark-summary', 'API scaling | recorded k6 summary', '19 Nov 2026 | 8 replicas + Redis + PgBouncer | formatted from the saved log')
box(s, 70, 225, 700, 155, '921.10 HTTP requests/s', 'Whole-run average, including ramps')
box(s, 810, 225, 720, 155, '1,000 iterations/s', 'Configured 10-minute plateau; 12-minute total run')
box(s, 70, 420, 700, 155, '11.70 ms p95 / 27.95 ms p99', 'Whole-run HTTP latency')
box(s, 810, 420, 720, 155, '0 failed / 663,132 requests', '0 dropped iterations; 656,399 completed')
text(s, 70, 640, 'An iteration chooses a read, list or write; create-then-delete uses two requests.', 27)
text(s, 70, 700, 'Path: Linux bridge inside Docker Desktop to the published port.', 27, '#aebed5')
text(s, 70, 750, 'Shared host; Docker VM CPU/RAM unrecorded. Not a capacity ceiling.', 27, '#aebed5')
text(s, 70, 830, 'Source: benchmarks/stress-published-linuxvm-10m.log', 24, '#65ddc0')

for name, shapes in pages.items():
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="900" viewBox="0 0 1600 900" role="img">', f'<title>{name.replace("-", " ")}</title>']
    for a in shapes:
        if a['kind'] == 'rect':
            parts.append(f'<rect x="{a["x"]}" y="{a["y"]}" width="{a["w"]}" height="{a["h"]}" fill="{a["color"]}"/>')
        elif a['kind'] == 'text':
            parts.append(f'<text x="{a["x"]}" y="{a["y"]+a["size"]}" font-family="Arial, sans-serif" font-size="{a["size"]}" fill="{a["color"]}">{escape(a["value"])}</text>')
        else:
            parts.append(f'<line x1="{a["x"]}" y1="{a["y"]}" x2="{a["xx"]}" y2="{a["yy"]}" stroke="{a["color"]}" stroke-width="4"/>')
    (OUT / f'{name}.svg').write_text('\n'.join(parts + ['</svg>']) + '\n', encoding='utf-8')
(OUT / 'drawing.json').write_text(json.dumps(pages), encoding='utf-8')
