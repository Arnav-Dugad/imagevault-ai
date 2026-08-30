[CmdletBinding()]
param(
    [switch]$CpuOnly,
    [switch]$NoBuild
)

$ErrorActionPreference = "Stop"
$repositoryRoot = (Resolve-Path -LiteralPath (Split-Path -Parent $PSScriptRoot)).Path
Push-Location $repositoryRoot
try {
    $gpuDetected = $false
    if (-not $CpuOnly -and (Get-Command nvidia-smi -ErrorAction SilentlyContinue)) {
        & nvidia-smi --query-gpu=name --format=csv,noheader 2>$null | Out-Null
        $gpuDetected = $LASTEXITCODE -eq 0
    }

    if ($gpuDetected) {
        Write-Host "NVIDIA GPU detected. Starting the CUDA worker with automatic CPU fallback..."
        $gpuArguments = @("compose", "-f", "docker-compose.yml", "-f", "docker-compose.gpu.yml", "up", "-d")
        if (-not $NoBuild) { $gpuArguments += "--build" }
        & docker @gpuArguments
        if ($LASTEXITCODE -eq 0) {
            Write-Host "ImageVault is running. The worker will use CUDA when healthy and fall back to CPU after a CUDA runtime failure."
            exit 0
        }
        Write-Warning "The GPU stack could not start. Rebuilding the worker for CPU mode."
    }

    $cpuArguments = @("compose", "up", "-d")
    if (-not $NoBuild -or $gpuDetected) { $cpuArguments += "--build" }
    & docker @cpuArguments
    if ($LASTEXITCODE -ne 0) { throw "Docker Compose could not start ImageVault." }
    Write-Host "ImageVault is running in CPU mode."
}
finally {
    Pop-Location
}
