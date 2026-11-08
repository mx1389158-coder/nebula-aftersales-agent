$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$webRoot = Join-Path $projectRoot "apps\web"
$composeProject = "nebula-e2e"
$testExitCode = 1

function Wait-Http([string]$Url) {
    for ($attempt = 0; $attempt -lt 180; $attempt++) {
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) { return }
        }
        catch { Start-Sleep -Seconds 1 }
    }
    throw "Timed out waiting for $Url"
}

try {
    Push-Location $projectRoot
    try {
        docker compose -p $composeProject -f docker-compose.yml -f docker-compose.test.yml up -d --build
        Wait-Http "http://127.0.0.1:5173"
    }
    finally { Pop-Location }

    $env:E2E_BASE_URL = "http://127.0.0.1:5173"
    Push-Location $webRoot
    try {
        & npx.cmd playwright test
        $testExitCode = $LASTEXITCODE
    }
    finally { Pop-Location }
}
finally {
    Push-Location $projectRoot
    try { docker compose -p $composeProject -f docker-compose.yml -f docker-compose.test.yml down -v --remove-orphans }
    finally { Pop-Location }
}

exit $testExitCode
