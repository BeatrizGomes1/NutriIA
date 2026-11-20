# Sobe o NutriIA para apresentação: o celular conecta no Hotspot móvel do
# notebook, baixa o APK por QR Code e o app usa o backend deste notebook.
#
# Uso: clique duas vezes em iniciar.bat (ou rode este script no PowerShell).
# Pré-requisito: o backend configurado conforme o COMO_RODAR.md.

$ErrorActionPreference = 'Stop'
$kit = $PSScriptRoot
$backend = Join-Path (Split-Path $kit -Parent) 'backend'
$python = Join-Path $backend '.venv\Scripts\python.exe'
$apk = Join-Path $kit 'publico\NutriIA.apk'
$HOTSPOT_IP = '192.168.137.1'

function Passo($texto) { Write-Host "`n>> $texto" -ForegroundColor Green }

# 1. Conferências
if (-not (Test-Path $python)) { throw "Backend não configurado: falta $python (veja COMO_RODAR.md)." }
if (-not (Test-Path $apk)) { throw "Falta o APK em $apk (gere com gerar-apk.ps1 ou copie o NutriIA.apk para a pasta publico)." }
$postgres = Get-Service 'postgresql*' -ErrorAction SilentlyContinue | Select-Object -First 1
if ($postgres -and $postgres.Status -ne 'Running') { throw "O PostgreSQL ($($postgres.Name)) está parado. Inicie o serviço e rode de novo." }

# 2. Firewall: libera as portas 8000 (backend) e 8080 (APK) só para a rede do hotspot.
Passo 'Firewall'
if (-not (Get-NetFirewallRule -DisplayName 'NutriIA apresentacao' -ErrorAction SilentlyContinue)) {
    Write-Host 'Criando a regra do firewall (o Windows vai pedir permissão de administrador)...'
    $regra = "New-NetFirewallRule -DisplayName 'NutriIA apresentacao' -Direction Inbound -Protocol TCP " +
             "-LocalPort 8000,8080 -RemoteAddress 192.168.137.0/24 -Action Allow -Profile Any | Out-Null"
    Start-Process powershell -Verb RunAs -Wait -ArgumentList '-NoProfile', '-Command', $regra
}
Write-Host 'Portas 8000 e 8080 liberadas para a rede do hotspot.'

# 3. Hotspot móvel
Passo 'Hotspot móvel'
while (-not (Get-NetIPAddress -IPAddress $HOTSPOT_IP -ErrorAction SilentlyContinue)) {
    Write-Host 'Ligue o "Hotspot móvel" do Windows (a tela de configurações vai abrir).' -ForegroundColor Yellow
    Start-Process 'ms-settings:network-mobilehotspot'
    Read-Host 'Depois de ligar, aperte Enter'
}
Write-Host "Hotspot ligado: este notebook é $HOTSPOT_IP na rede do hotspot."

# Lê nome e senha do hotspot para o QR de Wi-Fi (se não conseguir, a página mostra só o QR do app).
$ssid = $null; $senha = $null
try {
    Add-Type -AssemblyName System.Runtime.WindowsRuntime
    $null = [Windows.Networking.Connectivity.NetworkInformation, Windows.Networking.Connectivity, ContentType = WindowsRuntime]
    $null = [Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager, Windows.Networking.NetworkOperators, ContentType = WindowsRuntime]
    $perfil = [Windows.Networking.Connectivity.NetworkInformation]::GetInternetConnectionProfile()
    $config = [Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager]::CreateFromConnectionProfile($perfil).GetCurrentAccessPointConfiguration()
    $ssid = $config.Ssid; $senha = $config.Passphrase
} catch {
    Write-Host 'Não deu para ler o nome/senha do hotspot; a página vai mostrar só o QR do app.'
}
$json = @{ ssid = $ssid; senha = $senha } | ConvertTo-Json -Compress
Set-Content -Path (Join-Path $kit 'config.js') -Value "window.NUTRIIA_HOTSPOT = $json;" -Encoding UTF8

# 4. Backend aceitando conexões da rede (não só do próprio PC)
Passo 'Backend (porta 8000)'
$ocupada = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($ocupada) {
    Write-Host 'Já existe algo na porta 8000; encerrando para subir o backend aberto para a rede...'
    $ocupada | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
    Start-Sleep 1
}
Start-Process powershell -WorkingDirectory $backend -ArgumentList '-NoExit', '-Command',
    "`$host.UI.RawUI.WindowTitle='NutriIA backend'; & '$python' -m uvicorn app.main:app --host 0.0.0.0 --port 8000"

# 5. Servidor do APK (só a pasta publico fica acessível)
Passo 'Download do APK (porta 8080)'
if (-not (Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue)) {
    Start-Process powershell -WorkingDirectory $kit -ArgumentList '-NoExit', '-Command',
        "`$host.UI.RawUI.WindowTitle='NutriIA download do APK'; & '$python' '$(Join-Path $kit 'servir_apk.py')' 8080"
}

# 6. Espera o backend responder e abre a página com os QR Codes
Passo 'Conferindo'
$ok = $false
foreach ($i in 1..30) {
    try { Invoke-WebRequest "http://${HOTSPOT_IP}:8000/api/v1/health" -UseBasicParsing -TimeoutSec 2 | Out-Null; $ok = $true; break } catch { Start-Sleep 1 }
}
if (-not $ok) { throw 'O backend não respondeu em http://192.168.137.1:8000. Veja a janela "NutriIA backend".' }
Write-Host "Backend OK em http://${HOTSPOT_IP}:8000"
Write-Host "APK em http://${HOTSPOT_IP}:8080/NutriIA.apk"
Start-Process (Join-Path $kit 'qrcode.html')

Write-Host "`nTudo pronto! Mostre a página com os QR Codes. Para encerrar, feche as janelas 'NutriIA backend' e 'NutriIA download do APK'." -ForegroundColor Green
