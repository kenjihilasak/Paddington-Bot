$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$envPath = Join-Path $repoRoot ".env"

if (-not (Test-Path -LiteralPath $envPath)) {
    throw "No .env file found at $envPath"
}

foreach ($line in Get-Content -LiteralPath $envPath) {
    $trimmed = $line.Trim()
    if (-not $trimmed -or $trimmed.StartsWith("#") -or -not $trimmed.Contains("=")) {
        continue
    }

    $key, $value = $trimmed.Split("=", 2)
    $key = $key.Trim()
    $value = $value.Trim().Trim('"').Trim("'")
    [Environment]::SetEnvironmentVariable($key, $value, "Process")
}

if (-not $env:BUCKET) {
    throw "BUCKET is missing in .env"
}
if (-not $env:ENDPOINT) {
    throw "ENDPOINT is missing in .env"
}
if (-not $env:ACCESS_KEY_ID) {
    throw "ACCESS_KEY_ID is missing in .env"
}
if (-not $env:SECRET_ACCESS_KEY) {
    throw "SECRET_ACCESS_KEY is missing in .env"
}

$env:AWS_ACCESS_KEY_ID = $env:ACCESS_KEY_ID
$env:AWS_SECRET_ACCESS_KEY = $env:SECRET_ACCESS_KEY
$env:AWS_DEFAULT_REGION = if ($env:REGION) { $env:REGION } else { "auto" }

Write-Host "S3 env loaded from .env"
Write-Host "Bucket: $env:BUCKET"
Write-Host "Endpoint: $env:ENDPOINT"
Write-Host "Use: aws s3 ls s3://$env:BUCKET --endpoint-url $env:ENDPOINT"

# comand for windows: Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
# then: . .\scripts\s3_from_env.ps1
# listar todo: aws s3 ls s3://$env:BUCKET --recursive --endpoint-url $env:ENDPOINT
# eliminar todo: aws s3 rm s3://$env:BUCKET --recursive --endpoint-url $env:ENDPOINT