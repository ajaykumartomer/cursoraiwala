# Anti-script: split MergedScripts.txt back into original .bat files.
# Save this next to MergedScripts.txt, then run:
#   powershell -NoProfile -ExecutionPolicy Bypass -File ANTI.ps1
# Output goes to extracted_bats\  — MergedScripts.txt is never deleted.

$ErrorActionPreference = 'Stop'
$here = if ($PSScriptRoot) { $PSScriptRoot } else { (Get-Location).Path }
$in = Join-Path -LiteralPath $here 'MergedScripts.txt'
$outDir = Join-Path -LiteralPath $here 'extracted_bats'

if (-not (Test-Path -LiteralPath $in)) {
    Write-Host '[ERROR] MergedScripts.txt not found in this folder.'
    exit 1
}

New-Item -ItemType Directory -Force -Path $outDir | Out-Null

$before = [System.IO.File]::ReadAllBytes($in)
$text = [System.Text.Encoding]::UTF8.GetString($before)
if ($text.StartsWith([char]0xFEFF)) { $text = $text.Substring(1) }
$text = $text -replace "`r`n", "`n" -replace "`r", "`n"
$lines = $text.Split("`n")
if ($lines.Length -gt 0 -and $lines[$lines.Length - 1] -eq '') {
    $lines = $lines[0..($lines.Length - 2)]
}

$header = [regex]'^Script\s+\d+\s+\{(.+)\}\s*$'
$currentName = $null
$buf = New-Object System.Collections.Generic.List[string]
$skip = 0
$count = 0

function Save-Current {
    if ([string]::IsNullOrEmpty($script:currentName)) { return }
    while ($script:buf.Count -gt 0 -and [string]::IsNullOrWhiteSpace($script:buf[$script:buf.Count - 1])) {
        $script:buf.RemoveAt($script:buf.Count - 1)
    }
    $safe = [System.IO.Path]::GetFileName(($script:currentName -replace '\\', '/'))
    if (-not $safe.ToLowerInvariant().EndsWith('.bat')) { throw "bad name: $safe" }
    if ($safe -ieq 'MergedScripts.txt') { throw 'refusing to overwrite MergedScripts.txt' }
    $enc = New-Object System.Text.UTF8Encoding $false
    $body = [string]::Join("`r`n", $script:buf.ToArray())
    if ($script:buf.Count -gt 0) { $body += "`r`n" }
    [System.IO.File]::WriteAllText((Join-Path $outDir $safe), $body, $enc)
    Write-Host "[+] $safe"
    $script:count++
    $script:buf.Clear()
}

Write-Host 'DISINTEGRATING SCRIPTS'
Write-Host 'MergedScripts.txt is read-only. Output: extracted_bats\'
Write-Host ''

foreach ($line in $lines) {
    $m = $header.Match($line)
    if ($m.Success) {
        Save-Current
        $script:currentName = $m.Groups[1].Value
        $script:skip = 3
        $script:buf.Clear()
        continue
    }
    if ([string]::IsNullOrEmpty($script:currentName)) { continue }
    if ($script:skip -gt 0) {
        if ([string]::IsNullOrWhiteSpace($line)) { $script:skip--; continue }
        $script:skip = 0
    }
    $script:buf.Add($line)
}
Save-Current

$after = [System.IO.File]::ReadAllBytes($in)
if ($after.Length -ne $before.Length) { throw 'MergedScripts.txt changed' }

Write-Host ''
Write-Host "Total Scripts Extracted: $count"
Write-Host 'MergedScripts.txt left untouched.'
if ($count -eq 0) { exit 1 }
