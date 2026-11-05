# Gera o APK da apresentação (apontando para o notebook no Hotspot móvel)
# e copia para apresentacao\publico\NutriIA.apk. Precisa do Android Studio instalado.

$ErrorActionPreference = 'Stop'
$frontend = Join-Path (Split-Path $PSScriptRoot -Parent) 'frontend'
if (-not $env:JAVA_HOME) { $env:JAVA_HOME = 'C:\Program Files\Android\Android Studio\jbr' }

Push-Location $frontend
try {
    & .\gradlew.bat assembleDebug '-Pnutriia.apiBaseUrl=http://192.168.137.1:8000/api/v1/'
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao gerar o APK.' }
} finally {
    Pop-Location
}

$destino = Join-Path $PSScriptRoot 'publico'
New-Item -ItemType Directory -Force $destino | Out-Null
Copy-Item (Join-Path $frontend 'app\build\outputs\apk\debug\app-debug.apk') (Join-Path $destino 'NutriIA.apk') -Force
Write-Host "APK pronto em $destino\NutriIA.apk" -ForegroundColor Green
