@echo off
setlocal
cd /d "%~dp0"

:: ============================================
:: Split Merged .txt File Back to .bat Files
:: ============================================

echo ============================================
echo    BAT FILE SPLITTER (SAFE MODE)
echo ============================================
echo.

:: Set paths as environment variables so PowerShell reads them perfectly, even with spaces
set "inputFile=%~dp0MergedScripts.txt"
set "outFolder=%~dp0Restored_Scripts"

:: Check if the merged file exists
if not exist "%inputFile%" (
    echo [ERROR] "MergedScripts.txt" not found in this folder!
    pause
    exit /b
)

:: Create the output folder if it doesn't exist
if not exist "%outFolder%" mkdir "%outFolder%"

echo Reading merged file and extracting scripts...
echo Please wait...
echo.

:: PowerShell reads the environment variables directly, avoiding all quote/space crashing issues
powershell -NoProfile -ExecutionPolicy Bypass -Command "$inFile = $env:inputFile; $outDir = $env:outFolder; $lines = Get-Content -LiteralPath $inFile; $cur = $null; $buffer = @(); foreach ($line in $lines) { if ($line -match '^Script \d+\s+\{(.+?)\}') { if ($cur) { Set-Content -LiteralPath $cur -Value $buffer -Encoding Ascii }; $cur = Join-Path $outDir $Matches[1]; Write-Host '[+] Restored:' $Matches[1]; $buffer = @() } elseif ($cur) { $buffer += $line } }; if ($cur) { Set-Content -LiteralPath $cur -Value $buffer -Encoding Ascii }"

echo.
echo ============================================
echo    COMPLETED!
echo ============================================
echo All scripts have been restored to the "%outFolder%" folder.
echo MergedScripts.txt was not deleted.
echo.
pause
