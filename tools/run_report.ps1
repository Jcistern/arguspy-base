param(
  [string]$Marker = "test_regresion",
  [string]$AllureResultsDir = "allure-results",
  [string]$ReportDir = "reporte-html",
  [switch]$Headed
)

$ErrorActionPreference = "Stop"

Write-Host "1) Ejecutando pytest (-m $Marker) y generando allure-results..." -ForegroundColor Cyan
$pytestArgs = @("-m", $Marker, "--alluredir=$AllureResultsDir", "--clean-alluredir")
if ($Headed) { $pytestArgs += "--headed" }
python -m pytest @pytestArgs
$pytestExit = $LASTEXITCODE

if ($pytestExit -ne 0) {
  Write-Host "pytest falló (exit=$pytestExit). Se generará el reporte igualmente para inspección." -ForegroundColor Yellow
}

Write-Host "2) Generando reporte HTML en $ReportDir ..." -ForegroundColor Cyan
python -m reporting.generate_report --results $AllureResultsDir --output $ReportDir
$reportExit = $LASTEXITCODE
if ($reportExit -ne 0) { throw "generate_report falló (exit=$reportExit)." }

# El index.html es autocontenido (datos incrustados): se abre sin servidor HTTP.
$IndexPath = Join-Path (Resolve-Path $ReportDir) "index.html"
Write-Host "3) Abriendo reporte: $IndexPath" -ForegroundColor Cyan
Start-Process $IndexPath | Out-Null

exit $pytestExit
