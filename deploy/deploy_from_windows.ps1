param(
    [string]$Server = "72.62.37.145",
    [string]$User = "root",
    [string]$Domain = "exam.stud-life.com",
    [string]$LetsEncryptEmail = ""
)

$ErrorActionPreference = "Stop"
$Key = Join-Path $env:USERPROFILE ".ssh\examsl_deploy_ed25519"
$Archive = Join-Path $PSScriptRoot "examsl-release.zip"
$Remote = "$User@$Server"

if (-not (Test-Path $Key)) { throw "SSH-ключ не найден: $Key" }
& (Join-Path $PSScriptRoot "package_release.ps1")

scp -i $Key $Archive "${Remote}:/tmp/examsl-release.zip"
if ($LASTEXITCODE -ne 0) { throw "Не удалось загрузить архив." }
scp -i $Key (Join-Path $PSScriptRoot "deploy_examsl.sh") "${Remote}:/tmp/deploy_examsl.sh"
if ($LASTEXITCODE -ne 0) { throw "Не удалось загрузить серверный скрипт." }

$RemoteCommand = "chmod 700 /tmp/deploy_examsl.sh && DOMAIN='$Domain' LE_EMAIL='$LetsEncryptEmail' /tmp/deploy_examsl.sh"
ssh -t -i $Key $Remote $RemoteCommand
if ($LASTEXITCODE -ne 0) { throw "Серверное развёртывание завершилось ошибкой." }
