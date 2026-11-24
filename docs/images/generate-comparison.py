"""Render the completed controlled matrix as SVGs and a Windows PNG drawing manifest."""
import json
import math
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
DATA = ROOT / 'benchmarks/results/2026-11-24-matrix/comparison.json'
rows = json.loads(DATA.read_text(encoding='utf-8'))
configs = [('1-direct-no-cache', '1 replica, no cache', 'Direct PostgreSQL'),
           ('1-direct-redis', '1 replica + Redis', 'Direct PostgreSQL'),
           ('1-pool-redis', '1 replica + Redis', 'With PgBouncer'),
           ('3-pool-redis', '3 replicas + Redis', 'With PgBouncer'),
           ('8-pool-redis', '8 replicas + Redis', 'With PgBouncer')]
groups = {key: [r for r in rows if r['config'] == key] for key, _, _ in configs}
assert len(rows) == 10 and all(len(group) == 2 for group in groups.values()), 'Need all ten runs'
pages = {}
def text(s, x, y, value, size=28, color='#f5f8ff'):
    s.append(dict(kind='text', x=x, y=y, value=value, size=size, color=color))
def rect(s, x, y, w, h, color):
    s.append(dict(kind='rect', x=x, y=y, w=w, h=h, color=color))
def line(s, x, y, xx, yy, color):
    s.append(dict(kind='line', x=x, y=y, xx=xx, yy=yy, color=color))
def page(name, title, subtitle):
    s=[]
    pages[name]=s
    rect(s,0,0,1600,900,'#101827')
    text(s,70,45,title,46)
    text(s,70,115,subtitle,25,'#aebed5')
    return s
def interval(group,key):
    return f'{min(r[key] for r in group):.2f} - {max(r[key] for r in group):.2f}'

s=page('controlled-latency','Redis, pooling and replicas: measured latency',
       '24 Nov 2026 | two runs per configuration | same code, workload and Compose network')
max_power=max(1, math.ceil(math.log10(max(r['p99_ms'] for r in rows))))
for x,key,label,color in [(470,'p95_ms','p95 (ms)','#65ddc0'),(1030,'p99_ms','p99 (ms)','#f5ae70')]:
    text(s,x,175,label,32,color)
    for power in range(max_power+1):
        xx=x+power/max_power*430
        line(s,xx,235,xx,700,'#293b54')
        text(s,xx-8,210,str(10**power),19,'#aebed5')
    for i,(config,title,detail) in enumerate(configs):
        group=groups[config]
        y=280+i*90
        points=[x+math.log10(r[key])/max_power*430 for r in group]
        line(s,min(points),y,max(points),y,color)
        for n,xx in enumerate(points):
            rect(s,xx-5,y-10+n*10,10,10,color)
        text(s,x,y+15,interval(group,key),24,color)
for i,(config,title,detail) in enumerate(configs):
    y=260+i*90
    text(s,70,y,title,27)
    text(s,70,y+36,detail,22,'#aebed5')
text(s,70,740,'Logarithmic axes. Markers show individual runs; lines show observed ranges, not confidence intervals.',24)
text(s,70,785,'Whole-run latency includes ramps. Two-minute plateau at 1,000 iterations/s; failures retained.',24,'#aebed5')
text(s,70,830,'Shared Docker host: 12 logical CPUs / 11.54 GiB. Timing anomalies and raw results are documented.',24,'#aebed5')

s=page('controlled-summary','API scaling | benchmark highlights',
       '24 Nov 2026 | 5 configurations, 10 runs | 1,000 iterations/s offered plateau')
for i,config in enumerate(['1-direct-no-cache','1-direct-redis','1-pool-redis','8-pool-redis']):
    group=groups[config]
    x=70+(i%2)*740
    y=230+(i//2)*205
    label={'1-direct-no-cache':'1 replica, no cache','1-direct-redis':'1 replica + Redis',
           '1-pool-redis':'1 replica + Redis + PgBouncer','8-pool-redis':'8 replicas + Redis + PgBouncer'}[config]
    rect(s,x,y,700,170,'#21324b')
    text(s,x+24,y+20,label,29)
    text(s,x+24,y+66,'p95: '+interval(group,'p95_ms')+' ms',32,'#65ddc0')
    text(s,x+24,y+118,f'{sum(r["passed"] for r in group)}/2 passed; {sum(r["failed"] for r in group):,} failed HTTP; {sum(r["drops"] for r in group):,} drops',23,'#aebed5')
text(s,70,660,'Ranges cover both repetitions. HTTP errors and drops are summed across the pair.',26)
text(s,70,710,'Fixed offered load; this does not measure maximum capacity or prove linear scaling.',26,'#aebed5')
text(s,70,760,'12 logical CPUs / 11.54 GiB Docker RAM; k6 shares the host with the API stack.',26,'#aebed5')
text(s,70,830,'Evidence: benchmarks/results/2026-11-24-matrix | full five-configuration table in README',23,'#65ddc0')

for name,shapes in pages.items():
    parts=['<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="900" viewBox="0 0 1600 900" role="img">',f'<title>{name.replace("-"," ")}</title>']
    for a in shapes:
        if a['kind']=='rect':
            parts.append(f'<rect x="{a["x"]}" y="{a["y"]}" width="{a["w"]}" height="{a["h"]}" fill="{a["color"]}"/>')
        elif a['kind']=='text':
            parts.append(f'<text x="{a["x"]}" y="{a["y"]+a["size"]}" font-family="Arial, sans-serif" font-size="{a["size"]}" fill="{a["color"]}">{escape(a["value"])}</text>')
        else:
            parts.append(f'<line x1="{a["x"]}" y1="{a["y"]}" x2="{a["xx"]}" y2="{a["yy"]}" stroke="{a["color"]}" stroke-width="3"/>')
    (OUT/f'{name}.svg').write_text('\n'.join(parts+['</svg>'])+'\n',encoding='utf-8')
(OUT/'drawing-current.json').write_text(json.dumps(pages,indent=2)+'\n',encoding='utf-8')
