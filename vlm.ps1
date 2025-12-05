#!/usr/bin/env pwsh
$ErrorActionPreference = 'Stop'

$server = $null

Write-Host "=== Starting local server ==="

try {
    if (Test-Path "./frontend/app.py") {
        $server = Start-Process python -ArgumentList "./frontend/app.py" -PassThru
        Start-Sleep -Seconds 3
    } else {
        Write-Host "app.py not found!"
    }

    Write-Host "=== Running VLM Attacker ==="
    Write-Host ">>> Make sure the server URL is correctly set up"
    Write-Host ">>> Make sure the ollama URL is correctly set up"

    python ./vlm.py
}
finally {
    if ($server -and -not $server.HasExited) {
        Write-Host "Stopping local server (PID=$($server.Id))..."
        try {
            $server.Kill()
        } catch {}
    }

    Write-Host "=== Done ==="
}
