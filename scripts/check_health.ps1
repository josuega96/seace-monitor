param(
  [string]$BackendUrl = "http://localhost:8080/api/health",
  [string]$FrontendUrl = "http://localhost:5173"
)

Write-Host "[health] Verificando backend: $BackendUrl"
try {
  $backend = Invoke-WebRequest -Uri $BackendUrl -UseBasicParsing -TimeoutSec 10
  Write-Host "[health] Backend OK - status $($backend.StatusCode)"
} catch {
  Write-Host "[health] Backend FAIL - $($_.Exception.Message)"
}

Write-Host "[health] Verificando frontend: $FrontendUrl"
try {
  $frontend = Invoke-WebRequest -Uri $FrontendUrl -UseBasicParsing -TimeoutSec 10
  Write-Host "[health] Frontend OK - status $($frontend.StatusCode)"
} catch {
  Write-Host "[health] Frontend FAIL - $($_.Exception.Message)"
}

