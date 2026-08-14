@echo off
setlocal enabledelayedexpansion

:: ============================================
:: Merge All .bat Files into Single .txt File
:: ============================================

set "output=MergedScripts.txt"
set "counter=0"
set "thisScript=%~nx0"

:: Delete output file if it already exists
if exist "%output%" del "%output%"

echo.
echo ============================================
echo    BAT FILE MERGER
echo ============================================
echo.

:: Loop through all .bat files in current directory
for %%F in (*.bat) do (

    :: Skip this script itself to avoid recursion
    if /i not "%%F"=="%thisScript%" (

        set /a counter+=1

        :: Write the Script Header with original filename
        echo Script !counter!  {%%F}>>"%output%"

        :: 3 Enter spaces (blank lines) between name and script content
        echo.>>"%output%"
        echo.>>"%output%"
        echo.>>"%output%"

        :: Append the actual bat file content
        type "%%F">>"%output%"

        :: 10 Enter spaces (blank lines) between one script and another
        for /l %%i in (1,1,10) do (
            echo.>>"%output%"
        )

        echo [+] Merged: %%F
    )
)

echo.
echo ============================================
echo    COMPLETED!
echo ============================================
echo.
echo Total Scripts Merged: !counter!
echo Output File: %output%
echo.
pause
