# scripts/instalar_servicio_flask.ps1
# Instala Flask (Waitress) como servicio de Windows usando NSSM.
# Ejecutar en PowerShell como Administrador:
#   cd C:\michin_web
#   .\scripts\instalar_servicio_flask.ps1

$ErrorActionPreference = "Stop"

$RUTA_PROYECTO = "C:\michin_web"
$RUTA_PYTHON = "$RUTA_PROYECTO\venv\Scripts\python.exe"
$RUTA_SCRIPT = "$RUTA_PROYECTO\run_prod.py"
$NOMBRE_SERVICIO = "MichinFlask"
$LOG_DIR = "$RUTA_PROYECTO\logs"

Write-Host "=== Instalador de servicio Flask (El Michin) ===" -ForegroundColor Cyan
Write-Host ""

# Verificar admin
$es_admin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $es_admin) {
    Write-Host "ERROR: Debes ejecutar este script como Administrador." -ForegroundColor Red
    exit 1
}

# Crear carpeta de logs
if (-not (Test-Path $LOG_DIR)) {
    New-Item -ItemType Directory -Path $LOG_DIR | Out-Null
    Write-Host "Carpeta de logs creada: $LOG_DIR" -ForegroundColor Green
}

# Verificar nssm
$nssm = Get-Command nssm -ErrorAction SilentlyContinue
if (-not $nssm) {
    Write-Host "ERROR: NSSM no esta instalado." -ForegroundColor Red
    Write-Host "Descargalo de https://nssm.cc/download y agrega nssm.exe al PATH" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Alternativa rapida (ejecutar esto primero):" -ForegroundColor Yellow
    Write-Host '  Invoke-WebRequest -Uri "https://nssm.cc/release/nssm-2.24.zip" -OutFile "$env:TEMP\nssm.zip"' -ForegroundColor White
    Write-Host '  Expand-Archive -Path "$env:TEMP\nssm.zip" -DestinationPath "$env:TEMP\nssm" -Force' -ForegroundColor White
    Write-Host '  Copy-Item "$env:TEMP\nssm\nssm-2.24\win64\nssm.exe" "C:\Windows\System32\nssm.exe"' -ForegroundColor White
    exit 1
}

# Verificar si el servicio ya existe
$existe = Get-Service -Name $NOMBRE_SERVICIO -ErrorAction SilentlyContinue
if ($existe) {
    Write-Host "Servicio ya existe. Deteniendo y eliminando..." -ForegroundColor Yellow
    Stop-Service $NOMBRE_SERVICIO -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
    nssm remove $NOMBRE_SERVICIO confirm
    Start-Sleep -Seconds 2
}

# Verificar que Python y el script existen
if (-not (Test-Path $RUTA_PYTHON)) {
    Write-Host "ERROR: No se encontro Python en $RUTA_PYTHON" -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $RUTA_SCRIPT)) {
    Write-Host "ERROR: No se encontro run_prod.py en $RUTA_SCRIPT" -ForegroundColor Red
    exit 1
}

Write-Host "Instalando servicio: $NOMBRE_SERVICIO" -ForegroundColor Cyan

# Instalar servicio con NSSM
nssm install $NOMBRE_SERVICIO $RUTA_PYTHON $RUTA_SCRIPT
nssm set $NOMBRE_SERVICIO AppDirectory $RUTA_PROYECTO
nssm set $NOMBRE_SERVICIO DisplayName "Michin Flask (El Michin)"
nssm set $NOMBRE_SERVICIO Description "Servidor web Flask para El Michin - Puerto 5000"
nssm set $NOMBRE_SERVICIO Start SERVICE_AUTO_START

# Logs
nssm set $NOMBRE_SERVICIO AppStdout "$LOG_DIR\flask_stdout.log"
nssm set $NOMBRE_SERVICIO AppStderr "$LOG_DIR\flask_stderr.log"
nssm set $NOMBRE_SERVICIO AppRotateFiles 1
nssm set $NOMBRE_SERVICIO AppRotateOnline 1
nssm set $NOMBRE_SERVICIO AppRotateSeconds 86400
nssm set $NOMBRE_SERVICIO AppRotateBytes 10485760

# Reinicio automatico
nssm set $NOMBRE_SERVICIO AppExit Default Restart
nssm set $NOMBRE_SERVICIO AppRestartDelay 5000

Write-Host "Servicio instalado. Arrancando..." -ForegroundColor Cyan
Start-Service $NOMBRE_SERVICIO
Start-Sleep -Seconds 5

$estado = Get-Service $NOMBRE_SERVICIO
Write-Host ""
Write-Host "Estado del servicio:" -ForegroundColor Cyan
Write-Host "  Nombre: $($estado.Name)"
Write-Host "  Display: $($estado.DisplayName)"
Write-Host "  Status: $($estado.Status)" -ForegroundColor $(if ($estado.Status -eq 'Running') { 'Green' } else { 'Red' })
Write-Host ""

if ($estado.Status -eq 'Running') {
    Write-Host "OK - Servicio funcionando correctamente." -ForegroundColor Green
    Write-Host ""
    Write-Host "Prueba:" -ForegroundColor Yellow
    Write-Host "  http://localhost:5000" -ForegroundColor White
    Write-Host "  https://central.elmichin.com" -ForegroundColor White
    Write-Host ""
    Write-Host "Comandos utiles:" -ForegroundColor Yellow
    Write-Host "  Get-Service $NOMBRE_SERVICIO          # Ver estado"
    Write-Host "  Restart-Service $NOMBRE_SERVICIO      # Reiniciar"
    Write-Host "  Stop-Service $NOMBRE_SERVICIO         # Detener"
    Write-Host "  nssm edit $NOMBRE_SERVICIO            # Editar config"
    Write-Host "  nssm remove $NOMBRE_SERVICIO confirm  # Desinstalar"
} else {
    Write-Host "ERROR - El servicio no arranco. Revisa los logs en:" -ForegroundColor Red
    Write-Host "  $LOG_DIR\flask_stderr.log" -ForegroundColor White
}
