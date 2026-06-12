# Compila HymnChords en un único .exe portable.
# Uso:  ./build.ps1
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

# Usar el Python del entorno virtual si existe; si no, el del PATH.
$venvPy = Join-Path $root ".venv\Scripts\python.exe"
if (Test-Path $venvPy) { $py = $venvPy } else { $py = "python" }

Write-Host "Instalando dependencias de build..." -ForegroundColor Cyan
& $py -m pip install -r (Join-Path $root "requirements-build.txt")

# Generar el ícono si aún no existe.
$icon = Join-Path $root "assets\icon.ico"
if (-not (Test-Path $icon)) {
    Write-Host "Generando ícono..." -ForegroundColor Cyan
    & $py (Join-Path $root "tools\make_icon.py")
}

Write-Host "Empaquetando con PyInstaller..." -ForegroundColor Cyan
& $py -m PyInstaller (Join-Path $root "HymnChords.spec") --clean --noconfirm

$exe = Join-Path $root "dist\HymnChords.exe"
if (Test-Path $exe) {
    Write-Host "`nListo: $exe" -ForegroundColor Green
} else {
    Write-Host "`nLa compilación terminó pero no se encontró el .exe esperado." -ForegroundColor Red
    exit 1
}
