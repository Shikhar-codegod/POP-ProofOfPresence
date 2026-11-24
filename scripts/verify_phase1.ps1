$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$InfraDir = Join-Path $RepoRoot "pop\infra"
$EdgePython = Join-Path $RepoRoot "pop\edge\.venv\Scripts\python.exe"
$Video = if ($env:POP_VERIFY_VIDEO) { $env:POP_VERIFY_VIDEO } else { Join-Path $RepoRoot "pop\ml\clips\classroom_cctv_360p.mp4" }
$Config = if ($env:POP_VERIFY_CONFIG) { $env:POP_VERIFY_CONFIG } else { Join-Path $RepoRoot "pop\edge\config.local.yaml" }
$ApiBase = if ($env:POP_API_URL) { $env:POP_API_URL } else { "http://localhost:8000" }
$CentreId = if ($env:POP_CENTRE_ID) { $env:POP_CENTRE_ID } else { "a1000000-0000-4000-8000-000000000001" }

function Add-Result($Name, $Passed, $Detail) {
    $script:Results += [pscustomobject]@{ Check = $Name; Status = if ($Passed) { "PASS" } else { "FAIL" }; Detail = $Detail }
}

$Results = @()
$allPassed = $true

if (-not (Test-Path $EdgePython)) { Add-Result "Environment" $false "Edge Python venv not found" }
if (-not $env:POP_ADMIN_EMAIL -or -not $env:POP_ADMIN_PASSWORD) { Add-Result "Credentials" $false "POP_ADMIN_EMAIL or POP_ADMIN_PASSWORD is not set" }
if (-not $env:POP_DEVICE_KEY) { Add-Result "Device key" $false "POP_DEVICE_KEY is not set" }
if (-not (Test-Path $Config)) { Add-Result "Edge config" $false "Config not found" }
if (-not (Test-Path $Video)) { Add-Result "Test video" $false "Video not found" }

try {
    Push-Location $InfraDir
    $composeLines = & docker compose ps
    $composePassed = $LASTEXITCODE -eq 0 -and ($composeLines | Where-Object { $_ -match "unhealthy|Exit|dead" }).Count -eq 0
    Add-Result "Docker Compose services" $composePassed "docker compose ps"
    if (-not $composePassed) { throw "Docker Compose services are unavailable" }

    try {
        $health = Invoke-RestMethod -Uri "$ApiBase/health" -Method Get
        Add-Result "/health" ($health.status -eq "healthy") "GET /health"
    } catch {
        Add-Result "/health" $false "GET /health failed"
        throw
    }

    $loginBody = @{ email = $env:POP_ADMIN_EMAIL; password = $env:POP_ADMIN_PASSWORD } | ConvertTo-Json -Compress
    $login = Invoke-RestMethod -Uri "$ApiBase/api/v1/auth/login" -Method Post -ContentType "application/json" -Body $loginBody
    if (-not $login.access_token) { throw "Login returned no access token" }
    Add-Result "Admin login" $true "POST /api/v1/auth/login"
}
catch {
    $allPassed = $false
}
finally {
    Pop-Location
}

if ($Results.Status -contains "FAIL") { $allPassed = $false }

if ($allPassed -and (Test-Path $Config) -and (Test-Path $Video)) {
    $startTime = (Get-Date).ToUniversalTime().AddSeconds(-30).ToString("yyyy-MM-dd'T'HH:mm:ss'Z'")
    $edgeArgs = @($RepoRoot.ToString() + "\pop\edge\run_edge.py", "--config", $Config, "--video", $Video, "--start-time", $startTime)
    try {
        Push-Location $RepoRoot
        $countBefore = (& docker compose -f pop/infra/docker-compose.yml exec -T postgres psql -U pop_user -d pop_db -tAc "SELECT COUNT(*) FROM readings;" | Select-Object -First 1).Trim()
        $firstLog = & $EdgePython @edgeArgs 2>&1 | Out-String
        $first201 = ([regex]::Matches($firstLog, "Reading POST HTTP 201")).Count
        Add-Result "Edge first run" ($first201 -gt 0) "$first201 reading POST(s) returned HTTP 201"

        $countAfterFirst = (& docker compose -f pop/infra/docker-compose.yml exec -T postgres psql -U pop_user -d pop_db -tAc "SELECT COUNT(*) FROM readings;" | Select-Object -First 1).Trim()
        $secondLog = & $EdgePython @edgeArgs 2>&1 | Out-String
        $second200 = ([regex]::Matches($secondLog, "Reading POST HTTP 200")).Count
        Add-Result "Edge duplicate run" ($second200 -gt 0) "$second200 reading POST(s) returned HTTP 200"

        $countAfterSecond = (& docker compose -f pop/infra/docker-compose.yml exec -T postgres psql -U pop_user -d pop_db -tAc "SELECT COUNT(*) FROM readings;" | Select-Object -First 1).Trim()
        Add-Result "Reading count unchanged" ($countAfterFirst -eq $countAfterSecond) "Before=$countBefore; after first=$countAfterFirst; after second=$countAfterSecond"

        $csvPath = Join-Path $RepoRoot "pop\edge\output\readings.csv"
        $csvRows = Import-Csv $csvPath
        $csvStable = [int]$csvRows[-1].stable_count
        $headers = @{ Authorization = "Bearer $($login.access_token)" }
        $centre = Invoke-RestMethod -Uri "$ApiBase/api/v1/centres/$CentreId" -Headers $headers -Method Get
        $latestStable = $null
        foreach ($camera in $centre.cameras) {
            if ($camera.latest_reading) { $latestStable = [int]$camera.latest_reading.stable_count }
        }
        Add-Result "Latest stable_count match" ($latestStable -eq $csvStable) "API=$latestStable; CSV=$csvStable"
    } catch {
        Add-Result "Phase 1 verification" $false "Edge/API verification failed"
    } finally {
        Pop-Location
    }
}

$Results | Format-Table -AutoSize
if ($Results.Status -contains "FAIL") { exit 1 }
exit 0
