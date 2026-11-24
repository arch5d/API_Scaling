"""Validate retained k6 summaries and produce comparison data without hiding failed runs."""
import argparse
import json
from pathlib import Path

def summarize(root):
    rows = []
    for path in sorted(root.glob('*/run.json')):
        run = json.loads(path.read_text(encoding='utf-8'))
        if 'exit_code' not in run:
            continue
        summary = json.loads((path.parent / 'summary.json').read_text(encoding='utf-8'))
        m = summary['metrics']
        total = int(m['http_reqs']['count'])
        # k6 Rate 'passes' counts true observations; true means an HTTP failure here.
        failed = int(m['http_req_failed']['passes'])
        assert total == failed + int(m['http_req_failed']['fails'])
        hits = int(m.get('article_cache_hits', {}).get('count', 0))
        misses = int(m.get('article_cache_misses', {}).get('count', 0))
        drops = int(m.get('dropped_iterations', {}).get('count', 0))
        p95, p99 = m['http_req_duration']['p(95)'], m['http_req_duration']['p(99)']
        passed = failed / total < .01 and p95 < 250 and p99 < 500 and drops == 0
        assert passed == (run['exit_code'] == 0), f'Exit status/threshold mismatch: {path.parent}'
        samples = [json.loads(line) for line in (path.parent / 'resources.jsonl').read_text(encoding='utf-8').splitlines()]
        db_sessions = []
        for sample in samples:
            # The snapshot query itself occupies one active session.
            db_sessions.append(sum(int(line.split('|')[-1]) for line in sample['pg_connections'].splitlines()) - 1)
        rows.append(dict(run=path.parent.name, config=run['config'], repeat=run['repeat'],
                         rps=m['http_reqs']['rate'], p95_ms=p95, p99_ms=p99,
                         requests=total, failed=failed, drops=drops, passed=passed,
                         iterations=int(m['iterations']['count']), hits=hits, misses=misses,
                         cache_hit_percent=100*hits/(hits+misses) if hits+misses else None,
                         min_http_duration_ms=m['http_req_duration']['min'],
                         sampled_db_sessions_min=min(db_sessions), sampled_db_sessions_max=max(db_sessions)))
    return rows

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    rows = summarize(args.directory)
    (args.directory / 'comparison.json').write_text(json.dumps(rows, indent=2)+'\n', encoding='utf-8')
    lines = ['| Run | HTTP RPS | p95 (ms) | p99 (ms) | Failed / total | Dropped | Thresholds |',
             '| --- | ---: | ---: | ---: | ---: | ---: | --- |']
    for r in rows:
        lines.append(f'| [{r["run"]}]({r["run"]}/k6.log) | {r["rps"]:.2f} | {r["p95_ms"]:.2f} | {r["p99_ms"]:.2f} | {r["failed"]:,} / {r["requests"]:,} | {r["drops"]:,} | {"Pass" if r["passed"] else "Fail"} |')
    (args.directory / 'comparison.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    groups = {}
    for row in rows:
        groups.setdefault(row['config'], []).append(row)
    compact = ['| Config | HTTP RPS range | p95 range (ms) | p99 range (ms) | Failed / total | Drops | Passed |',
               '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    labels = {'1-direct-no-cache': '1 replica, no cache; direct DB',
              '1-direct-redis': '1 replica + Redis; direct DB',
              '1-pool-redis': '1 replica + Redis + PgBouncer',
              '3-pool-redis': '3 replicas + Redis + PgBouncer',
              '8-pool-redis': '8 replicas + Redis + PgBouncer'}
    for config, group in groups.items():
        def interval(key):
            return f'{min(r[key] for r in group):.2f}–{max(r[key] for r in group):.2f}'
        compact.append(f'| {labels[config]} | {interval("rps")} | {interval("p95_ms")} | {interval("p99_ms")} | {sum(r["failed"] for r in group):,} / {sum(r["requests"] for r in group):,} | {sum(r["drops"] for r in group):,} | {sum(r["passed"] for r in group)}/{len(group)} |')
    (args.directory / 'compact.md').write_text('\n'.join(compact)+'\n', encoding='utf-8')
    print('\n'.join(lines))

if __name__ == '__main__':
    main()
