$ErrorActionPreference = "Continue"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$InfraDir = Join-Path $RepoRoot "pop\infra"
$EdgePython = Join-Path $RepoRoot "pop\edge\.venv\Scripts\python.exe"
$Video = if ($env:POP_VERIFY_VIDEO) { $env:POP_VERIFY_VIDEO } else { Join-Path $RepoRoot "pop\ml\clips\classroom_cctv_360p.mp4" }
$Config = if ($env:POP_VERIFY_CONFIG) { $env:POP_VERIFY_CONFIG } else { Join-Path $RepoRoot "pop\edge\config.local.yaml" }
$ApiBase = if ($env:POP_API_URL) { $env:POP_API_URL } else { "http://localhost:8000" }
$CentreId = if ($env:POP_CENTRE_ID) { $env:POP_CENTRE_ID } else { "a1000000-0000-4000-8000-000000000001" }
$Results = @()

function Add-Result([string]$Name, [bool]$Passed, [string]$Detail) {
    $script:Results += [pscustomobject]@{
        Check = $Name
        Status = if ($Passed) { "PASS" } else { "FAIL" }
        Detail = $Detail
    }
}

function Mask-Stderr([string]$Text) {
    $Text = $Text -replace 'devkey_[A-Za-z0-9_-]+', 'devkey_[REDACTED]'
    $Text = $Text -replace 'eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+', '[REDACTED_JWT]'
    return ($Text -split "`r?`n" | Select-Object -Last 3) -join " | "
}

$composeLines = ""
$composeExit = 0
try {
    Push-Location $InfraDir
    $composeLines = (& docker compose --ansi never ps --format json 2>$null | Out-String)
    $composeExit = if (
        $composeLines -match "pop_backend" -and
        $composeLines -match "pop_postgres" -and
        $composeLines -match "pop_redis"
    ) { 0 } else { 1 }
} catch {
    $composeLines = $_.Exception.Message
    $composeExit = 1
} finally {
    if ((Get-Location).Path -eq $InfraDir) { Pop-Location }
}
$composePassed = $composeExit -eq 0 -and $composeLines -notmatch "unhealthy|not running"
Add-Result "Compose services" $composePassed ("docker compose ps exit=$composeExit")

$healthPassed = $false
$healthDetail = "GET /health not run"
try {
    $health = Invoke-RestMethod -Uri "$ApiBase/health" -Method Get -TimeoutSec 10
    $healthPassed = $health.status -eq "healthy"
    $healthDetail = "GET /health status=$($health.status)"
} catch {
    $healthDetail = "GET /health exit=1 detail=" + (Mask-Stderr $_.Exception.Message)
}
Add-Result "/health" $healthPassed $healthDetail

Add-Result "Edge config present" (Test-Path $Config) ("path=$Config")
$edgeKeyPresent = [bool]$env:POP_DEVICE_KEY
Add-Result "Edge key environment" $edgeKeyPresent "POP_DEVICE_KEY set=$edgeKeyPresent"

$login = $null
$loginPassed = $false
if (-not $env:POP_ADMIN_EMAIL -or -not $env:POP_ADMIN_PASSWORD) {
    Add-Result "Admin login" $false "POP_ADMIN_EMAIL or POP_ADMIN_PASSWORD is not set"
} else {
    try {
        $loginBody = @{ email = $env:POP_ADMIN_EMAIL; password = $env:POP_ADMIN_PASSWORD } | ConvertTo-Json -Compress
        $login = Invoke-RestMethod -Uri "$ApiBase/api/v1/auth/login" -Method Post -ContentType "application/json" -Body $loginBody -TimeoutSec 10
        $loginPassed = [bool]$login.access_token
        Add-Result "Admin login" $loginPassed "POST /api/v1/auth/login"
    } catch {
        Add-Result "Admin login" $false ("POST /api/v1/auth/login failed: " + (Mask-Stderr $_.Exception.Message))
    }
}

$firstPassed = $false
$secondPassed = $false
$countPassed = $false
$matchPassed = $false

if ((Test-Path $EdgePython) -and (Test-Path $Config) -and (Test-Path $Video) -and $edgeKeyPresent) {
    $cameraId = & $EdgePython -c "import yaml; d=yaml.safe_load(open(r'$Config',encoding='utf-8')); print(d['backend']['camera_id'])" 2>&1
    $cameraId = ($cameraId | Select-Object -First 1).ToString().Trim()

    Push-Location $RepoRoot
    try {
        $envValues = @{}
        foreach ($line in Get-Content (Join-Path $InfraDir ".env")) {
            if ($line -match '^([^#][^=]*)=(.*)$') {
                $envValues[$matches[1].Trim()] = $matches[2].Trim()
            }
        }
        $u = $envValues["POSTGRES_USER"]
        $d = $envValues["POSTGRES_DB"]

        Push-Location $InfraDir
        $countBeforeOutput = & docker compose exec -T postgres psql -U $u -d $d -tAc "select count(*) from readings where camera_id='$cameraId';" 2>$null
        $countBeforeRow = $countBeforeOutput | Select-Object -First 1
        $countBefore = if ($countBeforeRow) { $countBeforeRow.ToString().Trim() } else { "0" }
        Pop-Location

        $startTime = (Get-Date).ToUniversalTime().AddSeconds(-30).ToString("yyyy-MM-dd'T'HH:mm:ss'Z'")
        $firstLog = & $EdgePython (Join-Path $RepoRoot "pop\edge\run_edge.py") --config $Config --video $Video --start-time $startTime 2>&1 | Out-String
        $firstExit = $LASTEXITCODE
        $first201 = ([regex]::Matches($firstLog, "Reading POST HTTP 201")).Count
        $first401 = ([regex]::Matches($firstLog, "Reading POST HTTP 401")).Count
        $firstPassed = $firstExit -eq 0 -and $first201 -gt 0
        $firstDetail = "HTTP 201=$first201; HTTP 401=$first401; exit=$firstExit"
        if (-not $firstPassed) { $firstDetail += "; " + (Mask-Stderr $firstLog) }
        Add-Result "Edge first run" $firstPassed $firstDetail

        Push-Location $InfraDir
        $countAfterFirstOutput = & docker compose exec -T postgres psql -U $u -d $d -tAc "select count(*) from readings where camera_id='$cameraId';" 2>$null
        $countAfterFirstRow = $countAfterFirstOutput | Select-Object -First 1
        $countAfterFirst = if ($countAfterFirstRow) { $countAfterFirstRow.ToString().Trim() } else { "0" }
        Pop-Location

        $secondLog = & $EdgePython (Join-Path $RepoRoot "pop\edge\run_edge.py") --config $Config --video $Video --start-time $startTime 2>&1 | Out-String
        $secondExit = $LASTEXITCODE
        $second200 = ([regex]::Matches($secondLog, "Reading POST HTTP 200")).Count
        $second401 = ([regex]::Matches($secondLog, "Reading POST HTTP 401")).Count
        $secondPassed = $secondExit -eq 0 -and $second200 -gt 0
        $secondDetail = "HTTP 200=$second200; HTTP 401=$second401; exit=$secondExit"
        if (-not $secondPassed) { $secondDetail += "; " + (Mask-Stderr $secondLog) }
        Add-Result "Edge duplicate run" $secondPassed $secondDetail

        Push-Location $InfraDir
        $countAfterSecondOutput = & docker compose exec -T postgres psql -U $u -d $d -tAc "select count(*) from readings where camera_id='$cameraId';" 2>$null
        $countAfterSecondRow = $countAfterSecondOutput | Select-Object -First 1
        $countAfterSecond = if ($countAfterSecondRow) { $countAfterSecondRow.ToString().Trim() } else { "0" }
        Pop-Location
        $countPassed = $countAfterFirst -eq $countAfterSecond
        Add-Result "Reading count unchanged" $countPassed "before=$countBefore; after first=$countAfterFirst; after second=$countAfterSecond"

        if ($loginPassed) {
            $csvRows = Import-Csv (Join-Path $RepoRoot "pop\edge\output\readings.csv")
            $csvStable = [int]$csvRows[-1].stable_count
            $lastVideoSec = [double]$csvRows[-1].video_time_sec
            $parsedStart = [datetimeoffset]::Parse($startTime)
            $expectedUtc = $parsedStart.UtcDateTime.AddSeconds($lastVideoSec)
            $expectedTimestamp = $expectedUtc.ToString("yyyy-MM-dd'T'HH:mm:ss'Z'")
            Push-Location $InfraDir
            $exactOutput = & docker compose exec -T postgres psql -U $u -d $d -tAc "select stable_count from readings where camera_id='$cameraId' and timestamp='$expectedTimestamp'::timestamptz;" 2>$null
            Pop-Location
            $exactRow = $exactOutput | Select-Object -First 1
            $exactStable = if ($exactRow) { [int]$exactRow.ToString().Trim() } else { $null }
            $matchPassed = $null -ne $exactStable -and $exactStable -eq $csvStable
            Add-Result "Exact timestamp match" $matchPassed "timestamp=$expectedTimestamp; DB stable=$exactStable; CSV stable=$csvStable"
        } else {
            Add-Result "Exact timestamp match" $false "Skipped: admin login unavailable"
        }
    } catch {
        Add-Result "Edge/API verification" $false ("exit=$LASTEXITCODE; " + (Mask-Stderr $_.Exception.Message))
    } finally {
        Pop-Location
    }
} else {
    Add-Result "Edge first run" $false "Skipped: edge Python, config, video, or POP_DEVICE_KEY unavailable"
    Add-Result "Edge duplicate run" $false "Skipped: edge Python, config, video, or POP_DEVICE_KEY unavailable"
    Add-Result "Reading count unchanged" $false "Skipped: edge run unavailable"
    Add-Result "Exact timestamp match" $false "Skipped: edge run or admin login unavailable"
}

$Results | Format-Table -AutoSize -Wrap
if ($Results.Status -contains "FAIL") { exit 1 }
exit 0
