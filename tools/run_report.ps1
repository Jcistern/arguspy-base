param(
  [int]$Port = 8000,
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

Write-Host "3) Levantando servidor HTTP estático (necesario; no funciona file:// por restricciones del browser)..." -ForegroundColor Cyan
$serverCmd = "python -m http.server $Port -d `"$ReportDir`""
Start-Process -WindowStyle Normal -FilePath "powershell" -ArgumentList @("-NoExit","-Command",$serverCmd) | Out-Null

Start-Sleep -Milliseconds 600

$Url = "http://localhost:$Port/"
Write-Host "4) Abriendo reporte: $Url" -ForegroundColor Cyan
Start-Process $Url | Out-Null

Write-Host ""
Write-Host "Listo. Deja la ventana del servidor abierta mientras uses el reporte." -ForegroundColor Green

exit $pytestExit
