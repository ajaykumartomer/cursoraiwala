@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul 2>&1
title AKT Video Processor - Flipped Moving Repeat

:: ============================================================
::  CONFIGURATION
:: ============================================================
set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

set "INPUT_FOLDER=%SCRIPT_DIR%\Input Folder"
set "OUTPUT_FOLDER=%SCRIPT_DIR%\Output Folder"
set "AUDIO_FOLDER=%SCRIPT_DIR%\Audio to Add"
set "LIB_ROOT=C:\AKT Media Tools"
set "SITE_PACKAGES=%LIB_ROOT%\Lib\site-packages"

:: Safe names only. FFmpeg breaks on @ and # in the real title.
set "TEMP_INPUT=%SCRIPT_DIR%\_input.mp4"
set "TEMP_OUTPUT=%SCRIPT_DIR%\_output.mp4"
set "CONCAT_FILE=%SCRIPT_DIR%\audio_concat.txt"
set "NAME_FILE=%SCRIPT_DIR%\current_name.txt"

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
echo   Effect: Flipped Moving Repeat 
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
) else (
    echo  [OK] Pillow already installed
)
set "NEED_GENAI=NO"
if not exist "%SITE_PACKAGES%\google" if not exist "%SITE_PACKAGES%\google_genai" set "NEED_GENAI=YES"
if "!NEED_GENAI!"=="YES" (
    echo  [..] Installing google-genai...
    %PYTHON% -m pip install --upgrade --target "%SITE_PACKAGES%" google-genai >nul 2>&1
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

:: --- Folders ---
echo  [~] Checking folders...
echo.
if not exist "%INPUT_FOLDER%" (mkdir "%INPUT_FOLDER%" & echo  [+] Created: Input Folder) else (echo  [OK] Input Folder exists)
if not exist "%OUTPUT_FOLDER%" (mkdir "%OUTPUT_FOLDER%" & echo  [+] Created: Output Folder) else (echo  [OK] Output Folder exists)
if not exist "%AUDIO_FOLDER%" (mkdir "%AUDIO_FOLDER%" & echo  [+] Created: Audio to Add) else (echo  [OK] Audio to Add folder exists)
echo.

:: --- Audio Setup (Looping Playlist) ---
echo  [~] Building Audio Playlist...
set "AUDIO_COUNT=0"
set "USE_AUDIO=NO"
if exist "%CONCAT_FILE%" del "%CONCAT_FILE%" >nul 2>&1

for %%a in ("%AUDIO_FOLDER%\*.*") do (
    set /a AUDIO_COUNT+=1
    copy /Y "%%a" "%SCRIPT_DIR%\_audio_!AUDIO_COUNT!%%~xa" >nul 2>&1
    echo file '_audio_!AUDIO_COUNT!%%~xa' >> "%CONCAT_FILE%"
)

if !AUDIO_COUNT! gtr 0 (
    echo  [OK] Found !AUDIO_COUNT! audio file^(s^). Playlist created.
    set "USE_AUDIO=YES"
) else (
    echo  [WARN] No audio files found in: %AUDIO_FOLDER%
    echo         Processing WITHOUT background audio.
)
echo.

:: --- Count files ---
set "FILE_COUNT=0"
for /f "delims=" %%C in ('powershell -NoProfile -Command "@(Get-ChildItem -LiteralPath '%INPUT_FOLDER%' -File).Count"') do set "FILE_COUNT=%%C"

if %FILE_COUNT% equ 0 (
    echo  [ERROR] No files in: Input Folder
    pause
    exit /b 1
)
echo  [OK] Found %FILE_COUNT% video file(s) to process
echo.

:: ============================================================
::  PROCESS
:: ============================================================
echo ============================================================
echo   STARTING VIDEO PROCESSING
echo ============================================================
echo.

set /a PROCESSED=0
set /a FAILED=0
set "START_TIME=%time%"

:: Process sequentially based on file count, completely avoiding CMD string reading
for /L %%N in (1, 1, %FILE_COUNT%) do (
    echo  --------------------------------------------------------
    echo  [~] Processing Video %%N of %FILE_COUNT%
    echo  --------------------------------------------------------

    :: 1. Clean Staging
    if exist "%TEMP_INPUT%" del "%TEMP_INPUT%" >nul 2>&1
    if exist "%TEMP_OUTPUT%" del "%TEMP_OUTPUT%" >nul 2>&1
    if exist "%NAME_FILE%" del "%NAME_FILE%" >nul 2>&1

    :: 2. Stage using PowerShell (Moves file out of Input to Temp, securely saves its original name)
    powershell -NoProfile -Command "$f = Get-ChildItem -LiteralPath '%INPUT_FOLDER%' -File | Select-Object -First 1; if ($f) { Move-Item -LiteralPath $f.FullName -Destination '%TEMP_INPUT%' -Force; [System.IO.File]::WriteAllText('%NAME_FILE%', $f.Name, [System.Text.Encoding]::UTF8) }" >nul 2>&1

    if not exist "%TEMP_INPUT%" (
        echo  [FAIL] Cannot stage file. Skipping...
        set /a FAILED+=1
    ) else (
        
        :: 3. Process Video 
        if "!USE_AUDIO!"=="YES" (
            ffmpeg -y -i "%TEMP_INPUT%" -ss 4 -i "%TEMP_INPUT%" -stream_loop -1 -safe 0 -f concat -i "%CONCAT_FILE%" -filter_complex "[0:v]scale=iw:ih[v2];[1:v]crop=in_w/1.5:in_h/1.5:(in_w-out_w)/1.5+((in_w-out_w)/1.5)*sin(t*0.5):(in_h-out_h)/1.5+((in_h-out_h)/1.5)*sin(t*0.2),boxblur=1:1,scale=iw*1.5:ih*1.5,hflip[v1];[v2][v1]overlay=1:enable='gte(mod(t,5),3)':x=0:y=0;[0:a]atempo=1,bass=frequency=200:gain=-90,volume=+20dB,aecho=1:0.6:2:0.4,bass=g=3:f=110:w=20,bass=g=10:f=500:w=20,bass=g=3:f=300:w=30,bass=g=10:f=110:w=20,bass=g=20:f=110:w=40,firequalizer=gain_entry='entry(0,-23);entry(250,-11.5);entry(6000,0);entry(12000,8);entry(16000,16)',compand=attacks=7:decays=1:points=-90/-90 -70/-60 -15/-15 0/-10:soft-knee=1:volume=-70:gain=3,pan=stereo| FL < FL + 0.5*FC + 0.6*BL + 0.6*SL | FR < FR + 2*FC + 1*BR + 2*SR,highpass=f=300,lowpass=f=700,volume=6[a1];[2:a]volume=1[a2];[a1][a2]amix=duration=shortest" -vcodec libx264 -pix_fmt yuv420p -r 30 -g 60 -b:v 1550k -shortest -acodec aac -b:a 128k -ar 44100 -metadata title="" -metadata artist="" -metadata album_artist="" -metadata album="" -metadata date="" -metadata track="" -metadata genre="" -metadata publisher="" -metadata encoded_by="" -metadata copyright="" -metadata composer="" -metadata performer="" -metadata TIT1="" -metadata TIT3="" -metadata disc="" -metadata TKEY="" -metadata TBPM="" -metadata language="eng" -metadata encoder="" -threads 0 -preset ultrafast -crf 30 "%TEMP_OUTPUT%" >nul 2>&1
        ) else (
            ffmpeg -y -i "%TEMP_INPUT%" -ss 4 -i "%TEMP_INPUT%" -filter_complex "[0:v]scale=iw:ih[v2];[1:v]crop=in_w/1.5:in_h/1.5:(in_w-out_w)/1.5+((in_w-out_w)/1.5)*sin(t*0.5):(in_h-out_h)/1.5+((in_h-out_h)/1.5)*sin(t*0.2),boxblur=1:1,scale=iw*1.5:ih*1.5,hflip[v1];[v2][v1]overlay=1:enable='gte(mod(t,5),3)':x=0:y=0;[0:a]atempo=1,bass=frequency=200:gain=-90,volume=+20dB,aecho=1:0.6:2:0.4,bass=g=3:f=110:w=20,bass=g=10:f=500:w=20,bass=g=3:f=300:w=30,bass=g=10:f=110:w=20,bass=g=20:f=110:w=40,firequalizer=gain_entry='entry(0,-23);entry(250,-11.5);entry(6000,0);entry(12000,8);entry(16000,16)',compand=attacks=7:decays=1:points=-90/-90 -70/-60 -15/-15 0/-10:soft-knee=1:volume=-70:gain=3,pan=stereo| FL < FL + 0.5*FC + 0.6*BL + 0.6*SL | FR < FR + 2*FC + 1*BR + 2*SR,highpass=f=300,lowpass=f=700,volume=6" -vcodec libx264 -pix_fmt yuv420p -r 30 -g 60 -b:v 1550k -shortest -acodec aac -b:a 128k -ar 44100 -metadata title="" -metadata artist="" -metadata album_artist="" -metadata album="" -metadata date="" -metadata track="" -metadata genre="" -metadata publisher="" -metadata encoded_by="" -metadata copyright="" -metadata composer="" -metadata performer="" -metadata TIT1="" -metadata TIT3="" -metadata disc="" -metadata TKEY="" -metadata TBPM="" -metadata language="eng" -metadata encoder="" -threads 0 -preset ultrafast -crf 30 "%TEMP_OUTPUT%" >nul 2>&1
        )

        :: 4. Move finished file to Output with EXACT original name
        if exist "%TEMP_OUTPUT%" (
            powershell -NoProfile -Command "$name = [System.IO.File]::ReadAllText('%NAME_FILE%', [System.Text.Encoding]::UTF8); Move-Item -LiteralPath '%TEMP_OUTPUT%' -Destination (Join-Path '%OUTPUT_FOLDER%' $name) -Force" >nul 2>&1
            echo  [OK] Saved exact original file to Output folder.
            echo  [OK] Removed original from Input folder.
            set /a PROCESSED+=1
        ) else (
            echo  [FAIL] FFmpeg failed. Restoring original file to Input...
            powershell -NoProfile -Command "$name = [System.IO.File]::ReadAllText('%NAME_FILE%', [System.Text.Encoding]::UTF8); Move-Item -LiteralPath '%TEMP_INPUT%' -Destination (Join-Path '%INPUT_FOLDER%' $name) -Force" >nul 2>&1
            set /a FAILED+=1
        )
    )
    echo.
)

:: ============================================================
::  CLEANUP
:: ============================================================
timeout /t 1 /nobreak >nul
if exist "%TEMP_INPUT%" del "%TEMP_INPUT%" >nul 2>&1
if exist "%TEMP_OUTPUT%" del "%TEMP_OUTPUT%" >nul 2>&1
if exist "%CONCAT_FILE%" del "%CONCAT_FILE%" >nul 2>&1
if exist "%NAME_FILE%" del "%NAME_FILE%" >nul 2>&1
del "%SCRIPT_DIR%\_audio_*" >nul 2>&1

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
echo.
echo ============================================================
echo.
pause
exit /b
