# Compila Ilahi en un unico .exe portable.
# Uso:  ./build.ps1
# Nota: texto sin acentos a proposito (PowerShell 5.1 lee .ps1 como ANSI; asi se
# evita el mojibake en los mensajes).
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

# Ejecuta un comando nativo (python, pip, PyInstaller) de forma robusta en
# PowerShell 5.1: baja ErrorActionPreference mientras corre para que lo que el
# comando escriba en stderr (p. ej. el aviso "A new release of pip...") NO aborte
# el script, y decide el exito por el CODIGO DE SALIDA, no por el stderr.
function Invoke-Native([string]$Exe, [string[]]$ArgList) {
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $Exe @ArgList
    } finally {
        $ErrorActionPreference = $prev
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Fallo: $Exe $($ArgList -join ' ')  (codigo $LASTEXITCODE)"
    }
}

# Usar el Python del entorno virtual si existe; si no, el del PATH.
$venvPy = Join-Path $root ".venv\Scripts\python.exe"
if (Test-Path $venvPy) { $py = $venvPy } else { $py = "python" }

Write-Host "Instalando dependencias (runtime + build)..." -ForegroundColor Cyan
Invoke-Native $py @("-m", "pip", "install", "--disable-pip-version-check",
                    "-r", (Join-Path $root "requirements.txt"))
Invoke-Native $py @("-m", "pip", "install", "--disable-pip-version-check",
                    "-r", (Join-Path $root "requirements-build.txt"))

# Generar el icono si aun no existe.
$icon = Join-Path $root "assets\icon.ico"
if (-not (Test-Path $icon)) {
    Write-Host "Generando icono..." -ForegroundColor Cyan
    Invoke-Native $py @((Join-Path $root "tools\make_icon.py"))
}

Write-Host "Empaquetando con PyInstaller..." -ForegroundColor Cyan
Invoke-Native $py @("-m", "PyInstaller", (Join-Path $root "Ilahi.spec"),
                    "--clean", "--noconfirm")

$exe = Join-Path $root "dist\Ilahi.exe"
if (Test-Path $exe) {
    Write-Host "`nListo: $exe" -ForegroundColor Green
} else {
    Write-Host "`nLa compilacion termino pero no se encontro el .exe esperado." -ForegroundColor Red
    exit 1
}
