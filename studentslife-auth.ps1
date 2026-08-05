param(
    [string]$BaseUrl = "https://students-life.ru/api2/api/v1",
    [string]$Email = "manager@tmmail.ru",
    [string]$Password = "!Manager12345",
    [string]$FirstName = "Manager",
    [string]$LastName = "Test",
    [string]$Phone = "+99363995579",
    [string]$TokenFile = ".\\studentslife-token.json",
    [switch]$Register,
    [switch]$Login,
    [switch]$Refresh,
    [switch]$Me
)

function Save-TokenFile($data) {
    $data | ConvertTo-Json -Depth 10 | Set-Content -Path $TokenFile -Encoding utf8
}

function Load-TokenFile {
    if (Test-Path $TokenFile) {
        return Get-Content $TokenFile -Raw | ConvertFrom-Json
    }
    return $null
}

function Register-StudentLifeUser {
    $body = @{
        email = $Email
        first_name = $FirstName
        last_name = $LastName
        password = $Password
        password_confirm = $Password
        phone = $Phone
        whatsapp = $Phone
        language = "ru"
    } | ConvertTo-Json -Compress

    try {
        $response = Invoke-RestMethod `
            -Uri "$BaseUrl/accounts/register/" `
            -Method POST `
            -ContentType "application/json" `
            -Body $body
        Write-Host "Пользователь зарегистрирован:" -ForegroundColor Green
        $response | Format-List
    }
    catch {
        Write-Host "Регистрация не прошла. Возможно, пользователь уже существует." -ForegroundColor Yellow
        if ($_.Exception.Response) {
            $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
            $reader.BaseStream.Position = 0
            $reader.DiscardBufferedData()
            $reader.ReadToEnd()
        } else {
            Write-Host $_
        }
    }
}

function Login-StudentLifeUser {
    $body = @{
        username = $Email
        password = $Password
    } | ConvertTo-Json -Compress

    $response = Invoke-RestMethod `
        -Uri "$BaseUrl/auth/login/" `
        -Method POST `
        -ContentType "application/json" `
        -Body $body

    $tokenData = [ordered]@{
        base_url = $BaseUrl
        email = $Email
        access = $response.access
        refresh = $response.refresh
        saved_at = (Get-Date).ToString("s")
    }

    Save-TokenFile $tokenData
    Write-Host "Логин успешный. Токены сохранены в $TokenFile" -ForegroundColor Green
    $tokenData
}

function Refresh-StudentLifeAccessToken {
    $stored = Load-TokenFile
    if (-not $stored) {
        throw "Файл токенов не найден: $TokenFile"
    }

    $body = @{
        refresh = $stored.refresh
    } | ConvertTo-Json -Compress

    $response = Invoke-RestMethod `
        -Uri "$BaseUrl/auth/refresh/" `
        -Method POST `
        -ContentType "application/json" `
        -Body $body

    $stored.access = $response.access
    if ($response.refresh) {
        $stored.refresh = $response.refresh
    }
    $stored.saved_at = (Get-Date).ToString("s")

    Save-TokenFile $stored
    Write-Host "Access token обновлён." -ForegroundColor Green
    $stored
}

function Get-Me {
    $stored = Load-TokenFile
    if (-not $stored) {
        throw "Файл токенов не найден: $TokenFile"
    }

    try {
        Invoke-RestMethod `
            -Uri "$BaseUrl/accounts/me/" `
            -Headers @{ Authorization = "Bearer $($stored.access)" } `
            -Method GET
    }
    catch {
        Write-Host "Access token, вероятно, истёк. Пытаюсь обновить..." -ForegroundColor Yellow
        $stored = Refresh-StudentLifeAccessToken
        Invoke-RestMethod `
            -Uri "$BaseUrl/accounts/me/" `
            -Headers @{ Authorization = "Bearer $($stored.access)" } `
            -Method GET
    }
}

if ($Register) {
    Register-StudentLifeUser
}

if ($Login) {
    Login-StudentLifeUser
}

if ($Refresh) {
    Refresh-StudentLifeAccessToken
}

if ($Me) {
    Get-Me | Format-List
}