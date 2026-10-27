$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$webRoot = Join-Path $projectRoot "apps\web"
$pythonPath = Join-Path $projectRoot ".venv\Scripts\python.exe"
$nodePath = (Get-Command node.exe).Source
$vitePath = Join-Path $webRoot "node_modules\vite\bin\vite.js"
$apiProcess = $null
$webProcess = $null
$testExitCode = 1

function Wait-Http([string]$Url) {
    for ($attempt = 0; $attempt -lt 80; $attempt++) {
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 1
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
                return
            }
        }
        catch {
            Start-Sleep -Milliseconds 250
        }
    }
    throw "Timed out waiting for $Url"
}

try {
    $env:LLM_PROVIDER = "mock"
    $env:EMBEDDING_PROVIDER = "hash"
    $env:CROSS_ENCODER_ENABLED = "false"
    $env:LANGFUSE_ENABLED = "false"
    $env:VITE_API_PROXY_TARGET = "http://127.0.0.1:8100"
    $env:E2E_REUSE_SERVER = "1"

    $apiProcess = Start-Process -FilePath $pythonPath -ArgumentList @(
        "-m", "uvicorn", "apps.api.app.main:app", "--host", "127.0.0.1", "--port", "8100"
    ) -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru
    $webProcess = Start-Process -FilePath $nodePath -ArgumentList @(
        $vitePath, "--host", "127.0.0.1", "--port", "5174"
    ) -WorkingDirectory $webRoot -WindowStyle Hidden -PassThru

    Wait-Http "http://127.0.0.1:8100/api/v1/health"
    Wait-Http "http://127.0.0.1:5174"
    Push-Location $webRoot
    try {
        & npx.cmd playwright test
        $testExitCode = $LASTEXITCODE
    }
    finally {
        Pop-Location
    }
}
finally {
    foreach ($process in @($webProcess, $apiProcess)) {
        if ($null -ne $process -and -not $process.HasExited) {
            Stop-Process -Id $process.Id -Force
        }
    }
}

exit $testExitCode
