@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>&1
if %errorlevel%==0 (
  py -3 "%~dp0akt_video_processor.py" %*
  goto :done
)

where python >nul 2>&1
if %errorlevel%==0 (
  python "%~dp0akt_video_processor.py" %*
  goto :done
)

echo  [FAIL] Python not found. Install Python and enable the "py" launcher.
pause
exit /b 1

:done
if errorlevel 1 pause
endlocal
