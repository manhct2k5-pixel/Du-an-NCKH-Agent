[CmdletBinding(PositionalBinding = $false)]
param(
  [string]$Model = "qwen2.5:7b",
  [string]$FallbackModel = "qwen2.5:3b",
  [string]$Question,
  [string]$Folder,
  [int]$MaxFiles = 30,
  [int]$MaxCharsPerFile = 5000,
  [int]$MaxTotalChars = 90000,
  [switch]$ListOnly,
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$ExtraArgs
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

function Get-OllamaExe {
  $candidate = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"
  if (Test-Path $candidate) {
    return $candidate
  }

  $fromPath = Get-Command ollama -ErrorAction SilentlyContinue
  if ($fromPath) {
    return $fromPath.Path
  }

  throw "Khong tim thay ollama.exe. Hay cai Ollama truoc."
}

function Get-OllamaApiBaseUrl {
  $hostValue = $env:OLLAMA_HOST
  if ([string]::IsNullOrWhiteSpace($hostValue)) {
    return "http://127.0.0.1:11434"
  }

  $normalized = $hostValue.Trim()
  if ($normalized -notmatch "^https?://") {
    $normalized = "http://$normalized"
  }

  if ($normalized -match "^http://0\.0\.0\.0:(\d+)$") {
    return "http://127.0.0.1:$($Matches[1])"
  }

  if ($normalized -match "^http://\[\:\:\]:(\d+)$") {
    return "http://127.0.0.1:$($Matches[1])"
  }

  return $normalized.TrimEnd("/")
}

function Invoke-OllamaApiOnce {
  param(
    [string]$Prompt,
    [string]$Model,
    [string]$ApiBaseUrl
  )

  $payload = @{
    model = $Model
    prompt = $Prompt
    stream = $false
  } | ConvertTo-Json -Depth 6

  $response = Invoke-RestMethod -Method Post -Uri "$ApiBaseUrl/api/generate" -ContentType "application/json" -Body $payload -TimeoutSec 600
  if ($null -eq $response -or [string]::IsNullOrWhiteSpace($response.response)) {
    throw "Ollama API khong tra ve noi dung."
  }

  Write-Host $response.response.TrimEnd()
}

function Invoke-OllamaWithFallback {
  param(
    [string]$Prompt,
    [string]$PrimaryModel,
    [string]$SecondaryModel,
    [string]$ApiBaseUrl
  )

  try {
    Invoke-OllamaApiOnce -Prompt $Prompt -Model $PrimaryModel -ApiBaseUrl $ApiBaseUrl
    return 0
  }
  catch {
    Write-Host ""
    Write-Host ("Model {0} loi qua API: {1}" -f $PrimaryModel, $_.Exception.Message)
  }

  if (-not [string]::IsNullOrWhiteSpace($SecondaryModel) -and $SecondaryModel -ne $PrimaryModel) {
    Write-Host ""
    Write-Host ("Model {0} loi, thu fallback sang {1}..." -f $PrimaryModel, $SecondaryModel)
    try {
      Invoke-OllamaApiOnce -Prompt $Prompt -Model $SecondaryModel -ApiBaseUrl $ApiBaseUrl
      return 0
    }
    catch {
      Write-Host ""
      Write-Host ("Model {0} loi qua API: {1}" -f $SecondaryModel, $_.Exception.Message)
      return 1
    }
  }

  return 1
}

if (-not $ExtraArgs) {
  $ExtraArgs = @()
}

if ([string]::IsNullOrWhiteSpace($Folder) -and $ExtraArgs.Count -gt 0) {
  $candidateFolder = $ExtraArgs[0]
  if (Test-Path -Path $candidateFolder -PathType Container) {
    $Folder = $candidateFolder
    if ($ExtraArgs.Count -gt 1) {
      $ExtraArgs = $ExtraArgs[1..($ExtraArgs.Count - 1)]
    } else {
      $ExtraArgs = @()
    }
  }
}

if ($ExtraArgs.Count -gt 0) {
  $tailQuestion = ($ExtraArgs -join " ").Trim()
  if (-not [string]::IsNullOrWhiteSpace($tailQuestion)) {
    if ([string]::IsNullOrWhiteSpace($Question)) {
      $Question = $tailQuestion
    } else {
      $Question = ("$Question $tailQuestion").Trim()
    }
  }
}

if ($ListOnly -and [string]::IsNullOrWhiteSpace($Folder)) {
  throw "Khi dung -ListOnly, can cung cap -Folder."
}

if (-not $ListOnly -and [string]::IsNullOrWhiteSpace($Question)) {
  do {
    $Question = Read-Host "Nhap cau hoi Brain (vi du: tao y tuong alpha cho mean-reversion)"
    if ([string]::IsNullOrWhiteSpace($Question)) {
      Write-Host "Gia tri khong duoc de trong."
    }
  } while ([string]::IsNullOrWhiteSpace($Question))
}

$selected = @()
$totalChars = 0
$folderPath = ""

if (-not [string]::IsNullOrWhiteSpace($Folder)) {
  $folderPath = (Resolve-Path -Path $Folder -ErrorAction Stop).Path
  $extensions = @(
    ".txt", ".md", ".csv", ".json", ".yaml", ".yml", ".xml", ".ini", ".log",
    ".py", ".ipynb", ".js", ".ts", ".tsx", ".jsx", ".java", ".c", ".cpp",
    ".h", ".hpp", ".cs", ".go", ".rs", ".sql", ".ps1", ".bat"
  )

  $allFiles = Get-ChildItem -Path $folderPath -Recurse -File -ErrorAction SilentlyContinue |
    Where-Object { $extensions -contains $_.Extension.ToLowerInvariant() } |
    Sort-Object FullName

  foreach ($f in $allFiles) {
    if ($selected.Count -ge $MaxFiles) {
      break
    }

    try {
      $raw = Get-Content -Path $f.FullName -Raw -Encoding UTF8 -ErrorAction Stop
    }
    catch {
      continue
    }

    if ([string]::IsNullOrWhiteSpace($raw)) {
      continue
    }

    if ($raw.Length -gt $MaxCharsPerFile) {
      $raw = $raw.Substring(0, $MaxCharsPerFile)
    }

    if (($totalChars + $raw.Length) -gt $MaxTotalChars) {
      break
    }

    $totalChars += $raw.Length
    $relative = $f.FullName.Substring($folderPath.Length).TrimStart('\')
    $selected += [PSCustomObject]@{
      RelativePath = $relative
      Content = $raw
      Length = $raw.Length
    }
  }

  if ($ListOnly) {
    Write-Host ("Doc duoc {0} file context, tong {1} ky tu." -f $selected.Count, $totalChars)
    $selected | ForEach-Object {
      Write-Host ("- {0} ({1} chars)" -f $_.RelativePath, $_.Length)
    }
    exit 0
  }
}

$parts = New-Object System.Collections.Generic.List[string]
$parts.Add("Ban la Quant Research Coach cho WorldQuant Brain.")
$parts.Add("Muc tieu: giup nguoi dung hoc va tao y tuong alpha chat luong cao, ro rang, co the test duoc.")
$parts.Add("Tuân thu dao duc: khong huong dan gian lan, khong khang dinh truy cap du lieu bi mat.")
$parts.Add("Neu thieu thong tin, noi ro gia dinh.")
$parts.Add("")
$parts.Add("Format tra loi bat buoc:")
$parts.Add("1) Problem framing (asset universe, horizon, gia dinh)")
$parts.Add("2) 3 y tuong alpha (co intuition + uu/nhuoc diem)")
$parts.Add("3) Candidate expression/pseudocode de implement")
$parts.Add("4) Validation plan (in-sample, out-of-sample, stability, turnover)")
$parts.Add("5) Risk controls (neutralization, exposure, overfit checks)")
$parts.Add("6) Next iteration (2-3 buoc toi uu tiep)")

if (-not [string]::IsNullOrWhiteSpace($folderPath)) {
  $parts.Add("")
  $parts.Add("Folder context: $folderPath")
  $parts.Add("Chi dung context sau neu lien quan.")
  foreach ($item in $selected) {
    $parts.Add("")
    $parts.Add("[FILE] $($item.RelativePath)")
    $parts.Add($item.Content)
  }
}

$parts.Add("")
$parts.Add("Cau hoi nguoi dung:")
$parts.Add($Question)
$parts.Add("")
$parts.Add("Tra loi bang tieng Viet, ngan gon, thuc dung.")

$prompt = ($parts -join "`n")
$apiBaseUrl = Get-OllamaApiBaseUrl
$exitCode = Invoke-OllamaWithFallback -Prompt $prompt -PrimaryModel $Model -SecondaryModel $FallbackModel -ApiBaseUrl $apiBaseUrl
exit $exitCode
