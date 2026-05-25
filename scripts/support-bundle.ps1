param(
    [string]$OutputDir = "support-bundles"
)

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$bundleRoot = Join-Path $OutputDir "omnyx-$timestamp"

New-Item -ItemType Directory -Force -Path $bundleRoot | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $bundleRoot "logs") | Out-Null

$pathsToCapture = @(
    "infra/compose/docker-compose.yml",
    "infra/compose/.env.example",
    "infra/openapi/openapi.yaml",
    "infra/operations",
    "docs/build"
)

foreach ($path in $pathsToCapture) {
    if (Test-Path $path) {
        Copy-Item -Recurse -Force $path $bundleRoot
    }
}

Write-Host "Support bundle prepared at $bundleRoot"
