$requiredPaths = @(
    "docs/poc/16_POC_RUNBOOK.md",
    "docs/poc/17_TEST_PLAN.md",
    "docs/poc/30_ONBOARDING_NEW_SITE.md",
    "docs/build/02_ACCEPTANCE_GATE.md",
    "infra/compose/docker-compose.yml",
    "infra/openapi/openapi.yaml"
)

$missing = @()
foreach ($path in $requiredPaths) {
    if (-not (Test-Path $path)) {
        $missing += $path
    }
}

if ($missing.Count -gt 0) {
    Write-Error ("Release gate blocked. Missing: " + ($missing -join ", "))
    exit 1
}

Write-Host "Release gate document set present."
& powershell -ExecutionPolicy Bypass -File scripts/smoke.ps1
