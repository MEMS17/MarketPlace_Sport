param(
    [string]$EndDate = "2026-04-07",
    [int]$Days = 30,
    [int]$OrdersPerDay = 30000
)

$ErrorActionPreference = "Stop"

if ($Days -lt 1) {
    throw "Days must be positive."
}
if ($OrdersPerDay -lt 1) {
    throw "OrdersPerDay must be positive."
}

$end = [datetime]::ParseExact($EndDate, "yyyy-MM-dd", [Globalization.CultureInfo]::InvariantCulture)
$start = $end.AddDays(1 - $Days)
$startText = $start.ToString("yyyy-MM-dd")
$endText = $end.ToString("yyyy-MM-dd")
$expectedRows = $Days * $OrdersPerDay
$previousOrderCount = $env:MARKETPLACE_ORDERS_PER_DAY
$repoRoot = Split-Path -Parent $PSScriptRoot

Push-Location $repoRoot
try {
    $env:MARKETPLACE_ORDERS_PER_DAY = "$OrdersPerDay"
    docker compose up -d --build --force-recreate --wait api-marketplace
    if ($LASTEXITCODE -ne 0) {
        throw "Could not start api-marketplace with the load-test volume."
    }

    for ($offset = 0; $offset -lt $Days; $offset++) {
        $date = $start.AddDays($offset).ToString("yyyy-MM-dd")
        Write-Host "Loading $date ($OrdersPerDay orders)"
        $runOutput = & docker compose exec -T airflow-worker airflow dags test marketplace_orders_ingest_daily $date 2>&1
        if ($LASTEXITCODE -ne 0) {
            $runOutput | Select-Object -Last 80 | ForEach-Object { Write-Host $_ }
            throw "DAG test failed for $date. Re-running the script is safe because each date is loaded idempotently."
        }
    }

    $stats = & docker compose exec -T postgres-dwh psql -U marketplace -d dwh -At -c "SELECT COUNT(DISTINCT dt)::text || '|' || COUNT(*)::text FROM dwh.fact_orders WHERE dt BETWEEN '$startText' AND '$endText';"
    if ($LASTEXITCODE -ne 0) {
        throw "Could not verify the loaded DWH rows."
    }

    $parts = "$stats".Trim() -split "\|"
    if ([int]$parts[0] -ne $Days -or [int]$parts[1] -ne $expectedRows) {
        throw "Expected $Days dates and $expectedRows rows, found $($parts[0]) dates and $($parts[1]) rows."
    }

    Write-Host "Verified $($parts[1]) fact rows across $($parts[0]) dates ($startText to $endText)."
}
finally {
    if ($null -eq $previousOrderCount) {
        Remove-Item Env:MARKETPLACE_ORDERS_PER_DAY -ErrorAction SilentlyContinue
    }
    else {
        $env:MARKETPLACE_ORDERS_PER_DAY = $previousOrderCount
    }

    docker compose up -d --force-recreate --wait api-marketplace | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Could not restore api-marketplace to its previous order volume."
    }
    Pop-Location
}
