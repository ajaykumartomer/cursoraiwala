@echo off
setlocal
cd /d "%~dp0"

if not exist "MergedScripts.txt" (
    echo.
    echo [ERROR] MergedScripts.txt was not found in this folder.
    pause
    exit /b 1
)

echo.
echo ============================================
echo       DISINTEGRATING SCRIPTS
echo ============================================
echo.

:: CMD cannot split these files itself: ffmpeg lines contain | & ( ) %% and are
:: often longer than the 8191-character command limit. PowerShell reads them as
:: plain text and writes each block to the original .bat name inside { }.
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "& { Set-Location -LiteralPath '%~dp0'; $p='%~f0'; $t=Get-Content -LiteralPath $p -Raw; $m='<'+'<<PS>>>'; $i=$t.IndexOf($m); Invoke-Expression $t.Substring($i+$m.Length) }"
set "err=%ERRORLEVEL%"

echo.
echo ============================================
echo    COMPLETED!
echo ============================================
echo.
if not "%err%"=="0" (
    echo Split failed. If PowerShell is blocked, run: python SplitMergedScripts.py
    pause
    exit /b %err%
)
pause
exit /b 0

<<<PS>>>
$ErrorActionPreference = 'Stop'
$inputFile = Join-Path (Get-Location) 'MergedScripts.txt'
if (-not (Test-Path -LiteralPath $inputFile)) {
    Write-Host '[ERROR] MergedScripts.txt was not found in this folder.'
    exit 1
}

$bytes = [System.IO.File]::ReadAllBytes($inputFile)
$text = [System.Text.Encoding]::UTF8.GetString($bytes)
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
    $outPath = Join-Path (Get-Location) $script:currentName
    $enc = New-Object System.Text.UTF8Encoding $false
    $body = $script:buf.ToArray()
    $joined = [string]::Join("`r`n", $body)
    if ($body.Length -gt 0) { $joined += "`r`n" }
    [System.IO.File]::WriteAllText($outPath, $joined, $enc)
    $script:count++
    Write-Host "[+] Created: $($script:currentName)"
    $script:buf.Clear()
}

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

Write-Host ""
Write-Host "Total Scripts Extracted: $count"
if ($count -eq 0) { exit 1 }
exit 0
