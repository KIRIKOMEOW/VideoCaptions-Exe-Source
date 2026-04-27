$ErrorActionPreference = "Stop"

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = "python"
}

& $python -m pip --version *>$null
if ($LASTEXITCODE -ne 0) {
    & $python -m ensurepip --upgrade
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to enable pip for $python"
    }
}

& $python -m PyInstaller --version *>$null
if ($LASTEXITCODE -ne 0) {
    & $python -m pip install pyinstaller
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to install PyInstaller"
    }
}

& $python -m PyInstaller --clean --noconfirm VideoCaptions.spec
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed"
}

Write-Host ""
Write-Host "Done: dist\VideoCaptions.exe"
