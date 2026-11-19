param(
  [string]$Victim = 'api_scaling-api-2',
  [int]$StopAfterSeconds = 100
)

$ErrorActionPreference = 'Continue'
$log = Join-Path $PWD 'benchmarks/replica-failure-under-load.log'

Write-Host "Flushing Redis..."
docker exec api_scaling-redis-1 redis-cli FLUSHDB

Write-Host "Starting k6 stress (2m plateau) via $log..."
$job = Start-Job -ScriptBlock {
  param($workdir, $logPath, $scriptPath)
  Set-Location $workdir
  & docker run --rm -i --cpus=8 --memory=8g --network api_scaling_default `
    -v "${scriptPath}:/scripts" `
    -e BASE_URL=http://nginx `
    -e STRESS=true `
    -e STRESS_PLATEAU=2m `
    -e ACCESS_PATTERN=realistic `
    grafana/k6 run /scripts/baseline.js 2>&1 | Out-File -FilePath $logPath -Encoding utf8
} -ArgumentList $PWD.Path, $log, (Join-Path $PWD.Path 'loadtest')

Write-Host "Waiting $StopAfterSeconds seconds before stopping $Victim..."
Start-Sleep -Seconds $StopAfterSeconds
docker stop $Victim

Write-Host "Waiting for k6 to finish..."
Wait-Job $job | Out-Null
Receive-Job $job
Remove-Job $job

Write-Host "Restoring $Victim..."
docker compose up -d --scale api=3 api

Write-Host "=== k6 summary ==="
Get-Content $log -Tail 60
