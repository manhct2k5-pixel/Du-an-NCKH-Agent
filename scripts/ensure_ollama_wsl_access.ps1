param(
  [string]$Host = "0.0.0.0:11434",
  [string]$Model = "qwen2.5:3b",
  [int]$WaitSeconds = 30,
  [switch]$Restart,
  [switch]$PullModel,
  [switch]$Warmup
)

$ErrorActionPreference = "Stop"

$ollamaExe = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"
if (-not (Test-Path $ollamaExe)) {
  throw "Khong tim thay ollama.exe tai $ollamaExe"
}

if ($Host -notmatch ":(\d+)$") {
  throw "Host khong hop le: $Host. Vi du dung: 0.0.0.0:11434"
}

$port = [int]$Matches[1]
$apiUrl = "http://127.0.0.1:$port"
$env:OLLAMA_HOST = $Host
[Environment]::SetEnvironmentVariable("OLLAMA_HOST", $Host, "User")

function Test-OllamaApi {
  param([string]$Url)

  try {
    Invoke-RestMethod -Method Get -Uri "$Url/api/version" -TimeoutSec 2 | Out-Null
    return $true
  }
  catch {
    return $false
  }
}

function Get-OllamaListener {
  param([int]$Port)

  return Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
    Select-Object -First 1
}

function Wait-OllamaApi {
  param(
    [string]$Url,
    [int]$Seconds
  )

  $deadline = (Get-Date).AddSeconds($Seconds)
  while ((Get-Date) -lt $deadline) {
    if (Test-OllamaApi -Url $Url) {
      return $true
    }
    Start-Sleep -Milliseconds 500
  }

  return $false
}

$listener = Get-OllamaListener -Port $port
$apiReady = Test-OllamaApi -Url $apiUrl
$publicBind = $false
if ($listener) {
  $publicBind = $listener.LocalAddress -in @("0.0.0.0", "::")
}

$needRestart = $Restart -or (-not $listener) -or (-not $apiReady) -or (-not $publicBind)

if ($needRestart) {
  Get-Process ollama -ErrorAction SilentlyContinue | Stop-Process -Force
  Start-Sleep -Seconds 1

  $startInfo = New-Object System.Diagnostics.ProcessStartInfo
  $startInfo.FileName = $ollamaExe
  $startInfo.Arguments = "serve"
  $startInfo.UseShellExecute = $false
  $startInfo.CreateNoWindow = $true
  $startInfo.Environment["OLLAMA_HOST"] = $Host

  [System.Diagnostics.Process]::Start($startInfo) | Out-Null
}

if (-not (Wait-OllamaApi -Url $apiUrl -Seconds $WaitSeconds)) {
  throw "Ollama chua san sang tren $apiUrl sau $WaitSeconds giay."
}

$listener = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
  Where-Object { $_.LocalAddress -in @("0.0.0.0", "::") } |
  Select-Object -First 1

if (-not $listener) {
  throw "Ollama dang chay nhung chua bind 0.0.0.0/$port cho WSL."
}

if ($PullModel) {
  & $ollamaExe pull $Model
}

if ($Warmup) {
  $payload = @{
    model = $Model
    prompt = "warmup"
    stream = $false
    options = @{ num_predict = 1 }
  } | ConvertTo-Json -Depth 6

  Invoke-RestMethod -Method Post -Uri "$apiUrl/api/generate" -ContentType "application/json" -Body $payload -TimeoutSec 120 | Out-Null
}

Write-Output ("OLLAMA_OK host={0} api={1} model={2}" -f $Host, $apiUrl, $Model)
