param(
  [Parameter(Mandatory = $true)][string]$PromptFile,
  [string[]]$Images = @(),
  [string]$Model = "",
  [string]$Bin = ""
)
# Runs Codex CLI's built-in image_gen tool with a prompt read from a UTF-8 file.
# The working directory of the caller is where Codex saves results.
$ErrorActionPreference = 'Stop'
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$prompt = Get-Content -Raw -Encoding UTF8 $PromptFile
if (-not $Bin) {
  $root = 'C:\Users\K\AppData\Local\OpenAI\Codex\bin'
  $cand = Get-ChildItem $root -Directory |
    Where-Object { Test-Path (Join-Path $_.FullName 'codex.exe') } |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1
  if ($cand) { $Bin = Join-Path $cand.FullName 'codex.exe' } else { $Bin = "$env:APPDATA\npm\codex.cmd" }
}
$argList = @('exec', '--skip-git-repo-check', '-s', 'workspace-write')
if ($Model) { $argList += @('-m', $Model) }
$argList += '-'
if ($Images.Count -gt 0) { $argList += '-i'; $argList += $Images }
$prompt | & $Bin @argList
