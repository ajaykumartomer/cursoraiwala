@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

if not exist "MergedScripts.txt" (
    echo.
    echo [ERROR] MergedScripts.txt was not found in this folder.
    echo This splitter never deletes that file.
    pause
    exit /b 1
)

echo.
echo ============================================
echo       DISINTEGRATING SCRIPTS
echo ============================================
echo.
echo Input file is READ-ONLY. Output goes to extracted_bats\
echo.

where python >nul 2>&1
if not errorlevel 1 (
    python "%~dp0SplitMergedScripts.py"
    set "err=!ERRORLEVEL!"
    goto :done
)

where python3 >nul 2>&1
if not errorlevel 1 (
    python3 "%~dp0SplitMergedScripts.py"
    set "err=!ERRORLEVEL!"
    goto :done
)

:: CMD cannot parse ffmpeg lines. PowerShell reads MergedScripts.txt as text
:: and writes each block into extracted_bats\ using the original filename.
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "& { Set-Location -LiteralPath '%~dp0'; $p='%~f0'; $t=Get-Content -LiteralPath $p -Raw; $m='<'+'<<PS>>>'; $i=$t.IndexOf($m); if ($i -lt 0) { throw 'splitter body missing' }; Invoke-Expression $t.Substring($i+$m.Length) }"
set "err=%ERRORLEVEL%"

:done
echo.
if not "%err%"=="0" (
    echo Split failed. MergedScripts.txt was not deleted by this script.
    pause
    exit /b %err%
)
echo MergedScripts.txt was left untouched.
pause
exit /b 0

<<<PS>>>
$ErrorActionPreference = 'Stop'
$inputFile = Join-Path (Get-Location) 'MergedScripts.txt'
if (-not (Test-Path -LiteralPath $inputFile)) {
    Write-Host '[ERROR] MergedScripts.txt was not found in this folder.'
    exit 1
}

$sourceBefore = [System.IO.File]::ReadAllBytes($inputFile)
$text = [System.Text.Encoding]::UTF8.GetString($sourceBefore)
if ($text.StartsWith([char]0xFEFF)) { $text = $text.Substring(1) }
$text = $text -replace "`r`n", "`n" -replace "`r", "`n"
$lines = $text.Split("`n")
if ($lines.Length -gt 0 -and $lines[$lines.Length - 1] -eq '') {
    $lines = $lines[0..($lines.Length - 2)]
}

$outDir = Join-Path (Get-Location) 'extracted_bats'
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

$header = [regex]'^Script\s+\d+\s+\{(.+)\}\s*$'
$protected = @('mergedscripts.txt','mergeallbats.bat','splitmergedscripts.bat','splitmergedscripts.py')
$currentName = $null
$buf = New-Object System.Collections.Generic.List[string]
$skip = 0
$count = 0

function Get-SafeName([string]$name) {
    $base = [System.IO.Path]::GetFileName($name.Replace('\','/'))
    if ([string]::IsNullOrWhiteSpace($base)) { throw "unsafe filename: $name" }
    if ($protected -contains $base.ToLowerInvariant()) { throw "refusing protected file: $base" }
    if (-not $base.ToLowerInvariant().EndsWith('.bat')) { throw "refusing non-.bat output: $base" }
    return $base
}

function Save-Current {
    if ([string]::IsNullOrEmpty($script:currentName)) { return }
    while ($script:buf.Count -gt 0 -and [string]::IsNullOrWhiteSpace($script:buf[$script:buf.Count - 1])) {
        $script:buf.RemoveAt($script:buf.Count - 1)
    }
    $safe = Get-SafeName $script:currentName
    $outPath = Join-Path $outDir $safe
    $enc = New-Object System.Text.UTF8Encoding $false
    $body = $script:buf.ToArray()
    $joined = [string]::Join("`r`n", $body)
    if ($body.Length -gt 0) { $joined += "`r`n" }
    [System.IO.File]::WriteAllText($outPath, $joined, $enc)
    $script:count++
    Write-Host "[+] Created: extracted_bats\$safe"
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

$sourceAfter = [System.IO.File]::ReadAllBytes($inputFile)
if ($sourceAfter.Length -ne $sourceBefore.Length) {
    throw 'MergedScripts.txt changed during split'
}

Write-Host ""
Write-Host "Total Scripts Extracted: $count"
Write-Host 'Input left untouched: MergedScripts.txt'
Write-Host 'Output folder: extracted_bats'
if ($count -eq 0) { exit 1 }
exit 0
