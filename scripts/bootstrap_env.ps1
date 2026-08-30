[CmdletBinding()]
param(
    [string]$Destination = (Join-Path (Split-Path -Parent $PSScriptRoot) ".env"),
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$repositoryRoot = (Resolve-Path -LiteralPath (Split-Path -Parent $PSScriptRoot)).Path
$resolvedDestination = [System.IO.Path]::GetFullPath($Destination)
if (-not $resolvedDestination.StartsWith($repositoryRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Destination must remain inside the ImageVault repository."
}
if ((Test-Path -LiteralPath $resolvedDestination) -and -not $Force) {
    throw ".env already exists. Use -Force only if you intend to replace local secrets."
}

function New-HexSecret([int]$Bytes = 32) {
    $buffer = New-Object byte[] $Bytes
    $generator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $generator.GetBytes($buffer)
    }
    finally {
        $generator.Dispose()
    }
    return -join ($buffer | ForEach-Object { $_.ToString("x2") })
}

$templatePath = Join-Path $repositoryRoot ".env.example"
$content = Get-Content -Raw -LiteralPath $templatePath
$databasePassword = New-HexSecret 24
$minioSecret = New-HexSecret 24
$jwtSecret = New-HexSecret 48
$grafanaPassword = New-HexSecret 20
$content = $content.Replace("REPLACE_WITH_A_RANDOM_DATABASE_PASSWORD", $databasePassword)
$content = $content.Replace("REPLACE_WITH_A_RANDOM_MINIO_SECRET", $minioSecret)
$content = $content.Replace("REPLACE_WITH_AT_LEAST_48_RANDOM_CHARACTERS", $jwtSecret)
$content = $content.Replace("REPLACE_WITH_A_RANDOM_GRAFANA_PASSWORD", $grafanaPassword)
[System.IO.File]::WriteAllText($resolvedDestination, $content, [System.Text.UTF8Encoding]::new($false))
Write-Host "Created $resolvedDestination with independent random local secrets."
Write-Host "Keep this file private; it is excluded by .gitignore."
