@echo off
chcp 65001 >nul 2>&1
title AKT Video Processor - BG2
cd /d "%~dp0"

:: Libraries only in C:\AKT Media Tools
set "LIB=C:\AKT Media Tools"
set "SITE=%LIB%\Lib\site-packages"
if not exist "%SITE%" mkdir "%SITE%" 2>nul
echo ok>"%SITE%\.write_test" 2>nul
if not exist "%SITE%\.write_test" (
    net session >nul 2>&1
    if errorlevel 1 (
        echo Need Administrator to create: %LIB%
        powershell -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
        exit /b
    )
    echo Cannot write to %LIB%
    pause
    exit /b 1
)
del "%SITE%\.write_test" 2>nul

if not exist "_input" mkdir "_input"
if not exist "_output" mkdir "_output"
if not exist "aud" mkdir "aud"

where ffmpeg >nul 2>&1 || (echo FFmpeg not found in PATH.& pause & exit /b 1)
if not exist "aud\bg2.mp4" (echo Put bg2.mp4 in the aud folder.& pause & exit /b 1)

:: Copy each clip to _in.mp4 first. FFmpeg treats @ in the real filename
:: as "read options from file". Encode is the original one-liner.
for %%t in ("_input\*.*") do (
    if exist "%%~t" if not exist "%%~t\" (
        echo Processing: %%~nxt
        copy /y "%%~t" "_in.mp4" >nul
        ffmpeg -y -i "_in.mp4" -ss 4 -i "_in.mp4" -filter_complex "[0:v]scale=iw:ih[v2];[1:v]crop=in_w/1.5:in_h/1.5:(in_w-out_w)/1.5+((in_w-out_w)/1.5)*sin(t*0.5):(in_h-out_h)/1.5 +((in_h-out_h)/1.5)*sin(t*0.2),boxblur=1:1,scale=iw*1.5:ih*1.5,hflip[v1];[v2][v1]overlay=1:enable='gte(mod(t,5),3)':x=0:y=0;[0:a]atempo=1,bass=frequency=200:gain=-90,volume=+20dB,aecho=1:0.6:2:0.4,bass=g=3:f=110:w=20,bass=g=10:f=500:w=20,bass=g=3:f=300:w=30,bass=g=10:f=110:w=20,bass=g=20:f=110:w=40,firequalizer=gain_entry='entry(0,-23);entry(250,-11.5);entry(6000,0);entry(12000,8);entry(16000,16)',compand=attacks=7:decays=1:points=-90/-90 -70/-60 -15/-15 0/-10:soft-knee=1:volume=-70:gain=3,pan=stereo| FL < FL + 0.5*FC + 0.6*BL + 0.6*SL | FR < FR + 2*FC + 1*BR + 2*SR,highpass=f=300,lowpass=f=700,volume=6[a1];amovie=aud/bg2.mp4:loop=9999,volume=1[a2];[a1][a2]amix=duration=shortest" -vcodec libx264 -pix_fmt yuv420p -r 30 -g 60 -b:v 1550k -shortest -acodec aac -b:a 128k -ar 44100 -metadata title="" -metadata artist="" -metadata album_artist="" -metadata album="" -metadata date="" -metadata track="" -metadata genre="" -metadata publisher="" -metadata encoded_by="" -metadata copyright="" -metadata composer="" -metadata performer="" -metadata TIT1="" -metadata TIT3="" -metadata disc="" -metadata TKEY="" -metadata TBPM="" -metadata language="eng" -metadata encoder="" -threads 0 -preset ultrafast -crf 30 "_output\%%~nt.mp4"
        del "_in.mp4" >nul 2>&1
    )
)

echo Done.
pause
