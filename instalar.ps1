# Instalador de Kyuuri: deja todo listo en un equipo con Windows.
# Detecta la GPU, instala lo que falte y configura el asistente.
$ErrorActionPreference = "Stop"
$backend = Join-Path $PSScriptRoot "backend"
$python = Join-Path $backend "venv\Scripts\python.exe"

function Paso($texto) { Write-Host "`n>> $texto" -ForegroundColor Cyan }
function Bien($texto) { Write-Host "   OK: $texto" -ForegroundColor Green }
function Aviso($texto) { Write-Host "   Aviso: $texto" -ForegroundColor Yellow }
function Morir($texto) { Write-Host "`nERROR: $texto" -ForegroundColor Red; exit 1 }

Write-Host "===============================================" -ForegroundColor Cyan
Write-Host "  Instalador de Kyuuri - asistente 100% local" -ForegroundColor Cyan
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host "Se descargan entre 4 y 10 GB segun tu equipo. Puede tardar un rato."

# --- 1. Python ---
Paso "Buscando Python"
$pythonSistema = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $pythonSistema) {
  Aviso "No tienes Python. Lo instalo con winget."
  if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
    Morir "No encontre winget. Instala Python 3.11 o mas nuevo desde https://python.org y vuelve a ejecutar esto."
  }
  winget install --id Python.Python.3.13 -e --accept-source-agreements --accept-package-agreements
  $pythonSistema = (Get-Command python -ErrorAction SilentlyContinue).Source
  if (-not $pythonSistema) { Morir "Python quedo instalado pero hay que cerrar y abrir esta ventana. Ejecuta instalar.bat otra vez." }
}
Bien "Python en $pythonSistema"

# --- 2. GPU ---
Paso "Revisando la tarjeta grafica"
$vram = 0
try {
  $salida = & nvidia-smi --query-gpu=name,memory.total --format=csv,noheader,nounits 2>$null
  if ($LASTEXITCODE -eq 0 -and $salida) {
    $partes = ($salida -split "`n")[0] -split ","
    $vram = [math]::Round([int]$partes[1].Trim() / 1024, 1)
    Bien "$($partes[0].Trim()) con $vram GB"
  }
} catch { }
if ($vram -eq 0) { Aviso "Sin GPU NVIDIA: funcionara con el procesador, mas lento pero sirve." }

# --- 3. Entorno de Python ---
Paso "Preparando el entorno de Python"
if (-not (Test-Path $python)) { & $pythonSistema -m venv (Join-Path $backend "venv") }
& $python -m pip install --quiet --upgrade pip
Bien "Entorno listo"

Paso "Instalando PyTorch (esta es la descarga mas grande)"
if ($vram -ge 4) {
  & $python -m pip install --quiet torch --index-url https://download.pytorch.org/whl/cu128
} else {
  & $python -m pip install --quiet torch --index-url https://download.pytorch.org/whl/cpu
}
if ($LASTEXITCODE -ne 0) { Morir "Fallo la instalacion de PyTorch. Revisa tu conexion y reintenta." }
Bien "PyTorch instalado"

Paso "Instalando el resto de las librerias"
& $python -m pip install --quiet -r (Join-Path $backend "requirements.txt")
if ($LASTEXITCODE -ne 0) { Morir "Fallo la instalacion de librerias." }
Bien "Librerias instaladas"

# --- 4. Ollama (conversacion libre) ---
Paso "Revisando Ollama (para conversar, opcional)"
$ollama = (Get-Command ollama -ErrorAction SilentlyContinue).Source
if (-not $ollama) { $ollama = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe" }
if (-not (Test-Path $ollama)) {
  if (Get-Command winget -ErrorAction SilentlyContinue) {
    Aviso "Instalando Ollama"
    winget install --id Ollama.Ollama -e --accept-source-agreements --accept-package-agreements --silent
  } else {
    Aviso "Sin Ollama no podra conversar, solo ejecutar comandos. Puedes instalarlo luego desde https://ollama.com"
  }
}

# --- 5. Configuracion automatica ---
Paso "Configurando Kyuuri para este equipo"
Push-Location $backend
& $python -m app.configure --automatico
Pop-Location

# --- 6. Modelos ---
Paso "Descargando el modelo de conversacion"
$modelo = ""
$linea = Select-String -Path (Join-Path $backend ".env") -Pattern "^OLLAMA_MODEL=(.+)$" -ErrorAction SilentlyContinue | Select-Object -First 1
if ($linea) { $modelo = $linea.Matches[0].Groups[1].Value.Trim() }
if ((Test-Path $ollama) -and $modelo) {
  & $ollama pull $modelo
} else {
  Aviso "Sin modelo de conversacion: Kyuuri funcionara solo con comandos."
}

Paso "Preparando el modelo de voz y el cerebro"
Push-Location $backend
if (-not (Test-Path (Join-Path $backend "models\intent\config.json"))) {
  Write-Host "   Entrenando el modelo de intenciones (unos minutos)..."
  & $python -m training.train
}
& $python -m app.diagnose
Pop-Location

# --- 7. Acceso directo ---
Paso "Creando el acceso directo"
$lanzador = Join-Path $PSScriptRoot "Kyuuri.bat"
@"
@echo off
cd /d "%~dp0backend"
"%~dp0backend\venv\Scripts\python.exe" -m app.voice
pause
"@ | Set-Content -Path $lanzador -Encoding ASCII
$escritorio = [Environment]::GetFolderPath("Desktop")
$acceso = (New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $escritorio "Kyuuri.lnk"))
$acceso.TargetPath = $lanzador
$acceso.WorkingDirectory = $PSScriptRoot
$acceso.Save()
Bien "Acceso directo en el escritorio"

Write-Host "`n===============================================" -ForegroundColor Green
Write-Host "  Listo. Abre 'Kyuuri' en el escritorio y di:" -ForegroundColor Green
Write-Host "  'Kyuuri, que sabes hacer'" -ForegroundColor Green
Write-Host "===============================================" -ForegroundColor Green
