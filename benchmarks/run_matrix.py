"""Run isolated, sequential comparisons; retain every attempt and its exit status.

Requires Docker Desktop, Python 3, and PowerShell (host provenance on Windows).
Only the api-scaling-bench project's database/cache are reset. Development data is untouched.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ['docker', 'compose', '-f', str(ROOT / 'benchmarks/compose.yml')]
CONFIGS = [
    ('1-direct-no-cache', 1, False, False),
    ('1-direct-redis', 1, True, False),
    ('1-pool-redis', 1, True, True),
    ('3-pool-redis', 3, True, True),
    ('8-pool-redis', 8, True, True),
]

def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()

def run(args, env=None, check=True):
    result = subprocess.run(args, cwd=ROOT, env=env, capture_output=True, text=True,
                            encoding='utf-8', errors='replace')
    if check and result.returncode:
        raise RuntimeError(f'{args}: {result.stdout}\n{result.stderr}')
    return result.stdout.strip()

def save(path, data):
    path.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')

def monitor(stop, path, env):
    with path.open('w', encoding='utf-8') as out:
        while not stop.wait(15):
            ids = run(COMPOSE + ['ps', '-q'], env).splitlines() + ['api-scaling-bench-k6']
            entry = {'time_utc': now(), 'stats': run(['docker', 'stats', '--no-stream', '--format', '{{json .}}'] + ids, check=False),
                     'pg_connections': run(COMPOSE + ['exec', '-T', 'postgres', 'psql', '-U', 'api', '-d', 'api_scaling', '-Atc',
                         "SELECT state, count(*) FROM pg_stat_activity WHERE datname='api_scaling' GROUP BY state ORDER BY state;"], env, False),
                     'pools': run(COMPOSE + ['exec', '-T', '-e', 'PGPASSWORD=api', 'pgbouncer', 'psql', '-h', '127.0.0.1', '-p', '6432', '-U', 'api', '-d', 'pgbouncer', '-c', 'SHOW POOLS;'], env, False)}
            out.write(json.dumps(entry) + '\n')
            out.flush()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, help='New directory under benchmarks/results')
    parser.add_argument('--repeats', type=int, default=2)
    parser.add_argument('--plateau', default='2m')
    parser.add_argument('--only', choices=[c[0] for c in CONFIGS])
    args = parser.parse_args()
    out = (ROOT / 'benchmarks/results' / args.output).resolve()
    if not out.is_relative_to((ROOT / 'benchmarks/results').resolve()):
        raise ValueError('Output must be inside benchmarks/results')
    out.mkdir(parents=True, exist_ok=False)
    metadata = {'started_utc': now(), 'source_commit': run(['git', 'rev-parse', 'HEAD']),
                'working_tree': run(['git', 'status', '--short']), 'plateau': args.plateau,
                'repeats': args.repeats, 'path': 'k6 container -> Compose nginx -> API',
                'docker': json.loads(run(['docker', 'info', '--format', '{{json .}}'])),
                'compose_version': run(['docker', 'compose', 'version']),
                'host': run(['powershell', '-NoProfile', '-Command',
                  "@{cpu=Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors;ramBytes=(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory} | ConvertTo-Json -Depth 3"]),
                'source_hashes': {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in
                  ['src/app.js', 'src/server.js', 'loadtest/baseline.js', 'benchmarks/compose.yml', 'nginx.conf', 'db/seed.sql', 'db/schema.sql', 'package-lock.json']}}
    # Publish only resource/version fields, not Docker registry/proxy/host configuration.
    metadata['docker'] = {k: metadata['docker'][k] for k in ['NCPU', 'MemTotal', 'ServerVersion', 'OperatingSystem', 'Architecture', 'KernelVersion']}
    save(out / 'environment.json', metadata)
    print('Building isolated benchmark image...', flush=True)
    build = run(COMPOSE + ['build', 'api'])
    (out / 'build.txt').write_text(build, encoding='utf-8')
    metadata['k6_version'] = run(['docker', 'run', '--rm', 'grafana/k6', 'version'])
    metadata['images'] = {}
    for image in ['api-scaling-bench-api', 'postgres:16', 'redis:7-alpine', 'edoburu/pgbouncer:latest', 'nginx:1.27-alpine', 'grafana/k6:latest']:
        info = json.loads(run(['docker', 'image', 'inspect', image]))[0]
        metadata['images'][image] = {'id': info['Id'], 'digests': info['RepoDigests']}
    save(out / 'environment.json', metadata)
    configs = [c for c in CONFIGS if not args.only or c[0] == args.only]
    for repeat in range(1, args.repeats + 1):
        # Reverse the second pass to reduce a simple time/order confound.
        for name, replicas, cache, pool in (configs if repeat % 2 else list(reversed(configs))):
            label = f'{name}-r{repeat}'
            attempt = out / label
            attempt.mkdir()
            env = os.environ.copy()
            env.update(BENCH_DB_HOST='pgbouncer' if pool else 'postgres',
                       BENCH_DB_PORT='6432' if pool else '5432', BENCH_CACHE_ENABLED=str(cache).lower())
            print(f'{now()} Preparing {label}', flush=True)
            run(COMPOSE + ['stop', 'nginx', 'api'], env, False)
            run(COMPOSE + ['up', '-d', '--wait', 'postgres', 'redis', 'pgbouncer'], env)
            run(COMPOSE + ['restart', 'pgbouncer'], env)
            run(COMPOSE + ['exec', '-T', 'postgres', 'psql', '-v', 'ON_ERROR_STOP=1', '-U', 'api', '-d', 'api_scaling', '-c', 'TRUNCATE articles RESTART IDENTITY;'], env)
            run(COMPOSE + ['exec', '-T', 'postgres', 'psql', '-v', 'ON_ERROR_STOP=1', '-U', 'api', '-d', 'api_scaling', '-f', '/docker-entrypoint-initdb.d/002-seed.sql'], env)
            run(COMPOSE + ['exec', '-T', 'redis', 'redis-cli', 'FLUSHDB'], env)
            rows = run(COMPOSE + ['exec', '-T', 'postgres', 'psql', '-U', 'api', '-d', 'api_scaling', '-Atc', 'SELECT count(*) FROM articles;'], env)
            if rows != '100000':
                raise RuntimeError(f'Unexpected initial dataset size: {rows}')
            run(COMPOSE + ['up', '-d', '--wait', '--scale', f'api={replicas}', 'api', 'nginx'], env)
            run(COMPOSE + ['restart', 'nginx'], env)
            api_ids = run(COMPOSE + ['ps', '-q', 'api'], env).splitlines()
            if len(api_ids) != replicas:
                raise RuntimeError('Replica count mismatch')
            health = [json.loads(run(['docker', 'exec', api_id, 'node', '-e',
                        "fetch('http://127.0.0.1:3000/health').then(r=>r.text()).then(console.log)"])) for api_id in api_ids]
            if any(h['cache'] != ('ready' if cache else 'unavailable') for h in health):
                raise RuntimeError('Cache configuration mismatch')
            command = ['docker', 'run', '--rm', '--name', 'api-scaling-bench-k6', '--cpus=8', '--memory=8g',
                       '--network', 'api-scaling-bench_default', '-v', f'{ROOT / "loadtest"}:/scripts:ro',
                       '-v', f'{attempt}:/results', '-e', 'BASE_URL=http://nginx', '-e', 'STRESS=true',
                       '-e', f'STRESS_PLATEAU={args.plateau}', '-e', 'ACCESS_PATTERN=realistic',
                       '-e', 'PRE_VUS=300', '-e', 'MAX_VUS=1000', '-e', 'RANDOM_SEED=20261124',
                       'grafana/k6', 'run', '--quiet', '--no-color', '--summary-export=/results/summary.json', '/scripts/baseline.js']
            record = {'config': name, 'repeat': repeat, 'replicas': replicas, 'redis': cache, 'pgbouncer': pool,
                      'started_utc': now(), 'initial_rows': int(rows), 'health': health, 'command': command}
            save(attempt / 'run.json', record)
            stop = threading.Event()
            observer = threading.Thread(target=monitor, args=(stop, attempt / 'resources.jsonl', env), daemon=True)
            observer.start()
            print(f'{now()} Running {label} (90s ramp + {args.plateau} plateau + 30s cooldown)', flush=True)
            with (attempt / 'k6.log').open('w', encoding='utf-8') as log:
                result = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
            stop.set()
            observer.join(timeout=30)
            record.update(finished_utc=now(), exit_code=result.returncode,
                          final_rows=int(run(COMPOSE + ['exec', '-T', 'postgres', 'psql', '-U', 'api', '-d', 'api_scaling', '-Atc', 'SELECT count(*) FROM articles;'], env)))
            save(attempt / 'run.json', record)
            print(f'{now()} Finished {label}: exit {result.returncode}', flush=True)
    metadata['finished_utc'] = now()
    save(out / 'environment.json', metadata)
    run(COMPOSE + ['stop'])
    print(f'Complete. Evidence: {out}', flush=True)

if __name__ == '__main__':
    main()
