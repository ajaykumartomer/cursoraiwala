@echo off
setlocal enabledelayedexpansion

:: ============================================
:: Merge All .bat Files into Single .txt File
:: Never deletes MergedScripts.txt until a backup exists.
:: ============================================

cd /d "%~dp0"

set "output=MergedScripts.txt"
set "backup=MergedScripts.backup.txt"
set "tempout=MergedScripts.building.txt"
set "counter=0"
set "thisScript=%~nx0"

echo.
echo ============================================
echo    BAT FILE MERGER
echo ============================================
echo.

if exist "%tempout%" del "%tempout%"

:: Loop through .bat files in this folder only (not extracted_bats)
for %%F in (*.bat) do (

    :: Skip utility scripts so they are not merged into the archive
    if /i not "%%F"=="%thisScript%" if /i not "%%F"=="SplitMergedScripts.bat" (

        set /a counter+=1

        echo Script !counter!  {%%F}>>"%tempout%"
        echo.>>"%tempout%"
        echo.>>"%tempout%"
        echo.>>"%tempout%"

        type "%%F">>"%tempout%"

        for /l %%i in (1,1,10) do (
            echo.>>"%tempout%"
        )

        echo [+] Merged: %%F
    )
)

if !counter! equ 0 (
    echo [ERROR] No .bat files found to merge.
    echo MergedScripts.txt was not changed.
    pause
    exit /b 1
)

:: Backup the existing archive BEFORE replacing it
if exist "%output%" (
    copy /y "%output%" "%backup%" >nul
    echo [+] Backup saved: %backup%
)

copy /y "%tempout%" "%output%" >nul
del "%tempout%"

echo.
echo ============================================
echo    COMPLETED!
echo ============================================
echo.
echo Total Scripts Merged: !counter!
echo Output File: %output%
if exist "%backup%" echo Backup File: %backup%
echo.
pause
