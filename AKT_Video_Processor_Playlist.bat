@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul 2>&1
title AKT Video Processor - Flipped Moving Repeat (Playlist Audio)

:: ============================================================
::  CONFIGURATION
:: ============================================================
set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
cd /d "%SCRIPT_DIR%"

set "INPUT_FOLDER=%SCRIPT_DIR%\Input Folder"
set "OUTPUT_FOLDER=%SCRIPT_DIR%\Output Folder"
set "AUDIO_FOLDER=%SCRIPT_DIR%\Audio to Add"
set "FAILED_FOLDER=%SCRIPT_DIR%\_failed"
set "LIB_ROOT=C:\AKT Media Tools"
set "SITE_PACKAGES=%LIB_ROOT%\Lib\site-packages"

:: Temp on SAME DRIVE as script (so Move-Item cannot fail across disks)
set "TEMP_DIR=%SCRIPT_DIR%\_akt_temp"
set "TEMP_INPUT=%TEMP_DIR%\_input.mp4"
set "TEMP_OUTPUT=%TEMP_DIR%\_output.mp4"
set "CONCAT_FILE=%TEMP_DIR%\audio_concat.txt"
set "NAME_FILE=%TEMP_DIR%\current_name.txt"
set "FILTER_AUDIO=%SCRIPT_DIR%\akt_filter_playlist.txt"
set "FILTER_NOAUDIO=%SCRIPT_DIR%\akt_filter_playlist_noaudio.txt"
set "LOG_FILE=%SCRIPT_DIR%\ffmpeg_log.txt"

:: ============================================================
::  SOFT UAC
:: ============================================================
call :TestLibWrite
if "!LIB_OK!"=="YES" goto :MAIN_START

net session >nul 2>&1
if %errorlevel% equ 0 (
    echo.
    echo  [ERROR] Cannot write to: %LIB_ROOT%
    echo.
    pause
    exit /b 1
)

echo.
echo  ============================================================
echo  Administrator needed for library folder:
echo    %LIB_ROOT%
echo  Click YES on UAC prompt...
echo  ============================================================
echo.
powershell -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
exit /b

:TestLibWrite
set "LIB_OK=NO"
if not exist "%SITE_PACKAGES%" mkdir "%SITE_PACKAGES%" 2>nul
if not exist "%SITE_PACKAGES%" exit /b
echo ok> "%SITE_PACKAGES%\.write_test" 2>nul
if not exist "%SITE_PACKAGES%\.write_test" exit /b
del "%SITE_PACKAGES%\.write_test" 2>nul
set "LIB_OK=YES"
net session >nul 2>&1
if %errorlevel% equ 0 icacls "%LIB_ROOT%" /grant "%USERNAME%:(OI)(CI)F" /T /C >nul 2>&1
exit /b

:: ============================================================
::  MAIN
:: ============================================================
:MAIN_START
echo.
echo ============================================================
echo   AKT VIDEO PROCESSOR
echo   Effect: Flipped Moving Repeat (Playlist Audio)
echo ============================================================
echo.
echo  [OK] Library folder writable
echo.

:: --- Python ---
set "PYTHON="
where py >nul 2>&1 && set "PYTHON=py"
if not defined PYTHON where python >nul 2>&1 && set "PYTHON=python"
if not defined PYTHON (
    echo  [ERROR] Python not found in PATH.
    pause
    exit /b 1
)
echo  [OK] Python: %PYTHON%
%PYTHON% --version 2>nul
echo.

:: --- Libraries ---
echo  [~] Checking libraries...
echo.
set "NEED_PIL=NO"
if not exist "%SITE_PACKAGES%\PIL" if not exist "%SITE_PACKAGES%\Pillow" set "NEED_PIL=YES"
if "!NEED_PIL!"=="YES" (
    echo  [..] Installing Pillow...
    %PYTHON% -m pip install --upgrade --target "%SITE_PACKAGES%" Pillow >nul 2>&1
    if !errorlevel! equ 0 (echo  [OK] Pillow) else (echo  [WARN] Pillow issue)
) else (
    echo  [OK] Pillow already installed
)
set "NEED_GENAI=NO"
if not exist "%SITE_PACKAGES%\google" if not exist "%SITE_PACKAGES%\google_genai" set "NEED_GENAI=YES"
if "!NEED_GENAI!"=="YES" (
    echo  [..] Installing google-genai...
    %PYTHON% -m pip install --upgrade --target "%SITE_PACKAGES%" google-genai >nul 2>&1
    if !errorlevel! equ 0 (echo  [OK] google-genai) else (echo  [WARN] google-genai issue)
) else (
    echo  [OK] google-genai already installed
)
echo.

:: --- FFmpeg ---
where ffmpeg >nul 2>&1
if %errorlevel% neq 0 (
    echo  [ERROR] FFmpeg not found in PATH.
    pause
    exit /b 1
)
echo  [OK] FFmpeg found
echo.

if not exist "%FILTER_AUDIO%" (
    echo  [ERROR] Missing filter file: %FILTER_AUDIO%
    pause
    exit /b 1
)

:: --- Folders ---
echo  [~] Checking folders...
echo.
if not exist "%INPUT_FOLDER%" (mkdir "%INPUT_FOLDER%" & echo  [+] Created: Input Folder) else (echo  [OK] Input Folder exists)
if not exist "%OUTPUT_FOLDER%" (mkdir "%OUTPUT_FOLDER%" & echo  [+] Created: Output Folder) else (echo  [OK] Output Folder exists)
if not exist "%AUDIO_FOLDER%" (mkdir "%AUDIO_FOLDER%" & echo  [+] Created: Audio to Add) else (echo  [OK] Audio to Add folder exists)
if not exist "%FAILED_FOLDER%" mkdir "%FAILED_FOLDER%"
if exist "%TEMP_DIR%" rmdir /s /q "%TEMP_DIR%" >nul 2>&1
mkdir "%TEMP_DIR%"
echo.

:: --- Audio Setup (Looping Playlist) ---
:: Copy to _audio_1.ext, _audio_2.ext so concat never sees @ # spaces
echo  [~] Building Audio Playlist...
set "USE_AUDIO=NO"
set "AUDIO_COUNT=0"
powershell -NoProfile -Command ^
  "$td='%TEMP_DIR%'; $af='%AUDIO_FOLDER%'; $cf='%CONCAT_FILE%';" ^
  "if (Test-Path -LiteralPath $cf) { Remove-Item -LiteralPath $cf -Force };" ^
  "$i=0;" ^
  "Get-ChildItem -LiteralPath $af -File -ErrorAction SilentlyContinue | Sort-Object Name | ForEach-Object {" ^
  "  $i++; $dest = Join-Path $td ('_audio_' + $i + $_.Extension);" ^
  "  Copy-Item -LiteralPath $_.FullName -Destination $dest -Force;" ^
  "  Add-Content -LiteralPath $cf -Value ('file ' + [char]39 + ('_audio_' + $i + $_.Extension) + [char]39) -Encoding ascii" ^
  "}" >nul 2>&1

for /f "delims=" %%C in ('powershell -NoProfile -Command "$cf='%CONCAT_FILE%'; if (Test-Path -LiteralPath $cf) { @(Get-Content -LiteralPath $cf).Count } else { 0 }"') do set "AUDIO_COUNT=%%C"

if !AUDIO_COUNT! gtr 0 (
    echo  [OK] Found !AUDIO_COUNT! audio file^(s^). Playlist created.
    set "USE_AUDIO=YES"
) else (
    echo  [WARN] No audio files found in: %AUDIO_FOLDER%
    echo         Processing WITHOUT background audio.
)
echo.

:: --- Count files (LiteralPath so @ # names are counted) ---
set "FILE_COUNT=0"
for /f "delims=" %%C in ('powershell -NoProfile -Command "@(Get-ChildItem -LiteralPath '%INPUT_FOLDER%' -File).Count"') do set "FILE_COUNT=%%C"

if "%FILE_COUNT%"=="0" (
    echo  [ERROR] No files in: Input Folder
    pause
    exit /b 1
)
echo  [OK] Found %FILE_COUNT% video file(s) to process
echo.

if exist "%LOG_FILE%" del "%LOG_FILE%" >nul 2>&1

:: ============================================================
::  PROCESS
::  Move first remaining Input file to a safe temp name (queue).
::  On success: save to Output with the original name, original gone.
::  On fail: move original to _failed (do NOT put it back in Input,
::  or the next loop would retry the same file forever).
::  Filter graph is in a file so cmd.exe cannot treat | and < as pipe.
:: ============================================================
echo ============================================================
echo   STARTING VIDEO PROCESSING
echo ============================================================
echo.

set /a PROCESSED=0
set /a FAILED=0
set "START_TIME=%time%"

for /L %%N in (1, 1, %FILE_COUNT%) do (
    echo  --------------------------------------------------------
    echo  [~] Processing Video %%N of %FILE_COUNT%
    echo  --------------------------------------------------------

    if exist "%TEMP_INPUT%" del "%TEMP_INPUT%" >nul 2>&1
    if exist "%TEMP_OUTPUT%" del "%TEMP_OUTPUT%" >nul 2>&1
    if exist "%NAME_FILE%" del "%NAME_FILE%" >nul 2>&1

    powershell -NoProfile -Command "$f = Get-ChildItem -LiteralPath '%INPUT_FOLDER%' -File | Select-Object -First 1; if ($f) { Move-Item -LiteralPath $f.FullName -Destination '%TEMP_INPUT%' -Force; [System.IO.File]::WriteAllText('%NAME_FILE%', $f.Name, [System.Text.Encoding]::UTF8) }" >nul 2>&1

    if not exist "%TEMP_INPUT%" (
        echo  [FAIL] Cannot stage file to temp folder. Skipping...
        set /a FAILED+=1
    ) else (
        echo  [~] Encoding...
        if "!USE_AUDIO!"=="YES" (
            pushd "%TEMP_DIR%"
            ffmpeg -nostdin -y -i "_input.mp4" -ss 4 -i "_input.mp4" -stream_loop -1 -safe 0 -f concat -i "audio_concat.txt" -filter_complex_script "%FILTER_AUDIO%" -vcodec libx264 -pix_fmt yuv420p -r 30 -g 60 -b:v 1550k -shortest -acodec aac -b:a 128k -ar 44100 -metadata title="" -metadata artist="" -metadata album_artist="" -metadata album="" -metadata date="" -metadata track="" -metadata genre="" -metadata publisher="" -metadata encoded_by="" -metadata copyright="" -metadata composer="" -metadata performer="" -metadata TIT1="" -metadata TIT3="" -metadata disc="" -metadata TKEY="" -metadata TBPM="" -metadata language="eng" -metadata encoder="" -threads 0 -preset ultrafast -crf 30 "_output.mp4" >>"%LOG_FILE%" 2>&1
            popd
        ) else (
            pushd "%TEMP_DIR%"
            ffmpeg -nostdin -y -i "_input.mp4" -ss 4 -i "_input.mp4" -filter_complex_script "%FILTER_NOAUDIO%" -vcodec libx264 -pix_fmt yuv420p -r 30 -g 60 -b:v 1550k -shortest -acodec aac -b:a 128k -ar 44100 -metadata title="" -metadata artist="" -metadata album_artist="" -metadata album="" -metadata date="" -metadata track="" -metadata genre="" -metadata publisher="" -metadata encoded_by="" -metadata copyright="" -metadata composer="" -metadata performer="" -metadata TIT1="" -metadata TIT3="" -metadata disc="" -metadata TKEY="" -metadata TBPM="" -metadata language="eng" -metadata encoder="" -threads 0 -preset ultrafast -crf 30 "_output.mp4" >>"%LOG_FILE%" 2>&1
            popd
        )

        if exist "%TEMP_OUTPUT%" (
            powershell -NoProfile -Command "$name = [System.IO.File]::ReadAllText('%NAME_FILE%', [System.Text.Encoding]::UTF8).Trim(); Move-Item -LiteralPath '%TEMP_OUTPUT%' -Destination (Join-Path '%OUTPUT_FOLDER%' $name) -Force" >nul 2>&1
            echo  [OK] Saved to Output Folder with original name.
            set /a PROCESSED+=1
        ) else (
            echo  [FAIL] FFmpeg failed. Original moved to _failed
            echo         See: ffmpeg_log.txt
            powershell -NoProfile -Command "$name = [System.IO.File]::ReadAllText('%NAME_FILE%', [System.Text.Encoding]::UTF8).Trim(); if (Test-Path -LiteralPath '%TEMP_INPUT%') { Move-Item -LiteralPath '%TEMP_INPUT%' -Destination (Join-Path '%FAILED_FOLDER%' $name) -Force }" >nul 2>&1
            set /a FAILED+=1
        )
    )
    echo.
)

:: ============================================================
::  CLEANUP  (never delete _input.mp4 if a file is still staged)
:: ============================================================
if exist "%TEMP_INPUT%" (
    echo  [!] Leftover staged file found. Moving to _failed...
    powershell -NoProfile -Command "$name = 'recovered.mp4'; if (Test-Path -LiteralPath '%NAME_FILE%') { $name = [System.IO.File]::ReadAllText('%NAME_FILE%', [System.Text.Encoding]::UTF8).Trim() }; Move-Item -LiteralPath '%TEMP_INPUT%' -Destination (Join-Path '%FAILED_FOLDER%' $name) -Force" >nul 2>&1
)
timeout /t 1 /nobreak >nul
if exist "%TEMP_DIR%" rmdir /s /q "%TEMP_DIR%" >nul 2>&1

:: ============================================================
::  SUMMARY
:: ============================================================
echo ============================================================
echo   PROCESSING COMPLETE
echo ============================================================
echo.
echo  Start Time  : %START_TIME%
echo  End Time    : %time%
echo  Processed   : %PROCESSED%
echo  Failed      : %FAILED%
echo  Input       : %INPUT_FOLDER%
echo  Output      : %OUTPUT_FOLDER%
echo  Audio       : %AUDIO_FOLDER%
if %FAILED% gtr 0 (
    echo  Failed dir  : %FAILED_FOLDER%
    echo  FFmpeg log  : %LOG_FILE%
)
echo.
echo ============================================================
echo.
pause
exit /b
