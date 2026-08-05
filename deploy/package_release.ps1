$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Output = Join-Path $PSScriptRoot "examsl-release.zip"

if (Test-Path $Output) {
    Remove-Item -LiteralPath $Output -Force
}

Push-Location $ProjectRoot
try {
    tar.exe -a -c -f $Output `
        --exclude=.venv `
        --exclude=venv `
        --exclude=.git `
        --exclude=deploy `
        --exclude=staticfiles `
        --exclude='*/__pycache__' `
        --exclude='*.pyc' `
        .
}
finally {
    Pop-Location
}

if (-not (Test-Path $Output)) {
    throw "Не удалось создать архив релиза."
}

Write-Host "Релиз создан: $Output"
Write-Warning "Архив содержит текущую базу и секреты Firebase/.env. Не публикуйте его."
