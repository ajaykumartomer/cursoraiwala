@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul 2>&1
title AKT Video Processor - Flipped Moving Repeat (BG2)

:: ============================================================
::  CONFIGURATION
:: ============================================================
set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

set "INPUT_FOLDER=%SCRIPT_DIR%\Input Folder"
set "OUTPUT_FOLDER=%SCRIPT_DIR%\Output Folder"
set "AUDIO_FOLDER=%SCRIPT_DIR%\Audio to Add"
set "AUDIO_FILE=bg2.mp4"
set "LIB_ROOT=C:\AKT Media Tools"
set "SITE_PACKAGES=%LIB_ROOT%\Lib\site-packages"
set "TEMP_INPUT=%TEMP%\akt_video_temp_input.mp4"
set "TEMP_AUDIO=%TEMP%\akt_video_temp_audio.mp4"
set "TEMP_OUTPUT=%TEMP%\akt_video_temp_output.mp4"
set "FILTER_AUDIO=%SCRIPT_DIR%\akt_filter_bg2.txt"
set "FILTER_NOAUDIO=%SCRIPT_DIR%\akt_filter_bg2_noaudio.txt"
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
    echo          Even as Administrator.
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
echo   Effect: Flipped Moving Repeat (Series 2 - BG2)
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
echo.

:: --- Audio ---
set "AUDIO_PATH=%AUDIO_FOLDER%\%AUDIO_FILE%"
set "USE_AUDIO=NO"
if exist "%AUDIO_PATH%" (
    echo  [OK] Audio: %AUDIO_FILE%
    copy /y "%AUDIO_PATH%" "%TEMP_AUDIO%" >nul 2>&1
    if exist "%TEMP_AUDIO%" (
        set "USE_AUDIO=YES"
    ) else (
        echo  [WARN] Could not copy audio to temp
    )
) else (
    echo  [WARN] Audio not found: %AUDIO_PATH%
    echo         Processing WITHOUT background audio.
)
echo.

:: --- Count files ---
set "FILE_COUNT=0"
for %%f in ("%INPUT_FOLDER%\*.*") do (
    if exist "%%~f" if not exist "%%~f\" set /a FILE_COUNT+=1
)
if %FILE_COUNT% equ 0 (
    echo  [ERROR] No files in: Input Folder
    pause
    exit /b 1
)
echo  [OK] Found %FILE_COUNT% file(s) to process
echo.

if exist "%LOG_FILE%" del "%LOG_FILE%" >nul 2>&1

:: ============================================================
::  PROCESS
::  Input/audio are copied to ASCII temp names so @ and # in
::  the original filename cannot split the FFmpeg command.
::  The filter graph is loaded from a file so cmd.exe cannot
::  treat | and < inside pan= as pipe/redirect.
::  Background audio is a third -i input, not amovie='C:\...'.
:: ============================================================
echo ============================================================
echo   STARTING VIDEO PROCESSING
echo ============================================================
echo.

set /a PROCESSED=0
set /a FAILED=0
set "START_TIME=%time%"

for %%t in ("%INPUT_FOLDER%\*.*") do (
    if exist "%%~t" if not exist "%%~t\" (
        echo  --------------------------------------------------------
        echo  [~] Processing: %%~nxt
        echo  --------------------------------------------------------

        if exist "%TEMP_INPUT%" del "%TEMP_INPUT%" >nul 2>&1
        if exist "%TEMP_OUTPUT%" del "%TEMP_OUTPUT%" >nul 2>&1

        copy /y "%%~t" "%TEMP_INPUT%" >nul 2>&1

        if not exist "%TEMP_INPUT%" (
            echo  [FAIL] Cannot copy to temp file
            set /a FAILED+=1
            echo.
        ) else (
            if "!USE_AUDIO!"=="YES" (
                ffmpeg -y -i "%TEMP_INPUT%" -ss 4 -i "%TEMP_INPUT%" -stream_loop -1 -i "%TEMP_AUDIO%" -filter_complex_script "%FILTER_AUDIO%" -vcodec libx264 -pix_fmt yuv420p -r 30 -g 60 -b:v 1550k -shortest -acodec aac -b:a 128k -ar 44100 -metadata title="" -metadata artist="" -metadata album_artist="" -metadata album="" -metadata date="" -metadata track="" -metadata genre="" -metadata publisher="" -metadata encoded_by="" -metadata copyright="" -metadata composer="" -metadata performer="" -metadata TIT1="" -metadata TIT3="" -metadata disc="" -metadata TKEY="" -metadata TBPM="" -metadata language="eng" -metadata encoder="" -threads 0 -preset ultrafast -crf 30 "%TEMP_OUTPUT%" >>"%LOG_FILE%" 2>&1
            ) else (
                ffmpeg -y -i "%TEMP_INPUT%" -ss 4 -i "%TEMP_INPUT%" -filter_complex_script "%FILTER_NOAUDIO%" -vcodec libx264 -pix_fmt yuv420p -r 30 -g 60 -b:v 1550k -shortest -acodec aac -b:a 128k -ar 44100 -metadata title="" -metadata artist="" -metadata album_artist="" -metadata album="" -metadata date="" -metadata track="" -metadata genre="" -metadata publisher="" -metadata encoded_by="" -metadata copyright="" -metadata composer="" -metadata performer="" -metadata TIT1="" -metadata TIT3="" -metadata disc="" -metadata TKEY="" -metadata TBPM="" -metadata language="eng" -metadata encoder="" -threads 0 -preset ultrafast -crf 30 "%TEMP_OUTPUT%" >>"%LOG_FILE%" 2>&1
            )

            if exist "%TEMP_OUTPUT%" (
                copy /y "%TEMP_OUTPUT%" "%OUTPUT_FOLDER%\%%~nt.mp4" >nul 2>&1
            )

            if exist "%OUTPUT_FOLDER%\%%~nt.mp4" (
                echo  [OK] Done: %%~nt.mp4
                set /a PROCESSED+=1
            ) else (
                echo  [FAIL] Failed: %%~nxt
                echo         See: ffmpeg_log.txt
                set /a FAILED+=1
            )

            if exist "%TEMP_INPUT%" del "%TEMP_INPUT%" >nul 2>&1
            if exist "%TEMP_OUTPUT%" del "%TEMP_OUTPUT%" >nul 2>&1
            echo.
        )
    )
)

:: ============================================================
::  CLEANUP
:: ============================================================
if exist "%TEMP_INPUT%" del "%TEMP_INPUT%" >nul 2>&1
if exist "%TEMP_AUDIO%" del "%TEMP_AUDIO%" >nul 2>&1
if exist "%TEMP_OUTPUT%" del "%TEMP_OUTPUT%" >nul 2>&1

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
echo  Audio       : %AUDIO_PATH%
if %FAILED% gtr 0 (
    echo.
    echo  [!] FFmpeg errors saved to: ffmpeg_log.txt
)
echo.
echo ============================================================
echo.
pause
exit /b
