$checks = @(
    "http://localhost:8000/healthz",
    "http://localhost:8080",
    "http://localhost:3000"
)

foreach ($url in $checks) {
    try {
        $response = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 5
        Write-Host "[OK] $url -> $($response.StatusCode)"
    }
    catch {
        Write-Host "[WARN] $url -> $($_.Exception.Message)"
    }
}
