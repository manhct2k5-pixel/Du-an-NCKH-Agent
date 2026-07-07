[CmdletBinding(PositionalBinding = $false)]
param(
  [string]$Model = "qwen2.5:3b",
  [string]$Folder,
  [string]$Question,
  [int]$MaxFiles = 40,
  [int]$MaxCharsPerFile = 6000,
  [int]$MaxTotalChars = 120000,
  [switch]$ListOnly,
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$ExtraArgs
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

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

if ([string]::IsNullOrWhiteSpace($Folder)) {
  throw "Folder khong duoc de trong."
}

if (-not $ListOnly -and [string]::IsNullOrWhiteSpace($Question)) {
  throw "Question khong duoc de trong."
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

$folderPath = Resolve-Path -Path $Folder -ErrorAction Stop
$folderPath = $folderPath.Path

$extensions = @(
  ".txt", ".md", ".csv", ".json", ".yaml", ".yml", ".xml", ".ini", ".log",
  ".py", ".ipynb", ".js", ".ts", ".tsx", ".jsx", ".java", ".c", ".cpp",
  ".h", ".hpp", ".cs", ".go", ".rs", ".sql", ".ps1", ".bat"
)

$allFiles = Get-ChildItem -Path $folderPath -Recurse -File -ErrorAction SilentlyContinue |
  Where-Object { $extensions -contains $_.Extension.ToLowerInvariant() } |
  Sort-Object FullName

if (-not $allFiles -or $allFiles.Count -eq 0) {
  throw "Khong tim thay file text/phu hop trong folder: $folderPath"
}

$selected = @()
$totalChars = 0

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

if (-not $selected -or $selected.Count -eq 0) {
  throw "Khong doc duoc noi dung file nao tu folder: $folderPath"
}

Write-Host ("Doc duoc {0} file, tong {1} ky tu context." -f $selected.Count, $totalChars)

if ($ListOnly) {
  $selected | ForEach-Object {
    Write-Host ("- {0} ({1} chars)" -f $_.RelativePath, $_.Length)
  }
  exit 0
}

$parts = New-Object System.Collections.Generic.List[string]
$parts.Add("Ban la tro ly phan tich file local.")
$parts.Add("Chi duoc tra loi dua tren context ben duoi. Neu thieu du lieu thi noi ro.")
$parts.Add("Folder: $folderPath")
$parts.Add("")
$parts.Add("=== CONTEXT FILES ===")

foreach ($item in $selected) {
  $parts.Add("")
  $parts.Add("[FILE] $($item.RelativePath)")
  $parts.Add($item.Content)
}

$parts.Add("")
$parts.Add("=== CAU HOI ===")
$parts.Add($Question)
$parts.Add("")
$parts.Add("Tra loi ngan gon, neu can thi trich dan ten file lien quan.")

$prompt = ($parts -join "`n")
$apiBaseUrl = Get-OllamaApiBaseUrl
$payload = @{
  model = $Model
  prompt = $prompt
  stream = $false
} | ConvertTo-Json -Depth 6

$response = Invoke-RestMethod -Method Post -Uri "$apiBaseUrl/api/generate" -ContentType "application/json" -Body $payload -TimeoutSec 600
if ($null -eq $response -or [string]::IsNullOrWhiteSpace($response.response)) {
  throw "Ollama API khong tra ve noi dung."
}

Write-Host $response.response.TrimEnd()
exit 0
