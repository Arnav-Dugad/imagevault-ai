[CmdletBinding()]
param(
    [switch]$CpuOnly,
    [switch]$NoBuild
)

$ErrorActionPreference = "Stop"
$repositoryRoot = (Resolve-Path -LiteralPath (Split-Path -Parent $PSScriptRoot)).Path
Push-Location $repositoryRoot
try {
    $composeArguments = @("compose", "-f", "docker-compose.yml")
    if (Test-Path -LiteralPath "frontend/dist/index.html") {
        $composeArguments += @("-f", "docker-compose.download.yml")
    }
    $gpuDetected = $false
    if (-not $CpuOnly -and (Get-Command nvidia-smi -ErrorAction SilentlyContinue)) {
        & nvidia-smi --query-gpu=name --format=csv,noheader 2>$null | Out-Null
        $gpuDetected = $LASTEXITCODE -eq 0
    }

    if ($gpuDetected) {
        Write-Host "NVIDIA GPU detected. Starting the CUDA worker with automatic CPU fallback..."
        $gpuArguments = $composeArguments + @("-f", "docker-compose.gpu.yml", "up", "-d")
        if (-not $NoBuild) { $gpuArguments += "--build" }
        & docker @gpuArguments
        if ($LASTEXITCODE -eq 0) {
            Write-Host "ImageVault is running. The worker will use CUDA when healthy and fall back to CPU after a CUDA runtime failure."
            exit 0
        }
        Write-Warning "The GPU stack could not start. Rebuilding the worker for CPU mode."
    }

    $cpuArguments = $composeArguments + @("up", "-d")
    if (-not $NoBuild -or $gpuDetected) { $cpuArguments += "--build" }
    & docker @cpuArguments
    if ($LASTEXITCODE -ne 0) { throw "Docker Compose could not start ImageVault." }
    Write-Host "ImageVault is running in CPU mode."
}
finally {
    Pop-Location
}
