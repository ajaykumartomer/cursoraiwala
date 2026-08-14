@echo off
cd /d "%~dp0"
if not exist "MergedScripts.txt" (
    echo [ERROR] MergedScripts.txt not found in this folder.
    pause
    exit /b 1
)
echo Splitting MergedScripts.txt into extracted_bats\
echo MergedScripts.txt will NOT be deleted.
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0ANTI.ps1"
echo.
pause
