@echo off
cd /d "%~dp0"
python instagram_downloader.py %*
if errorlevel 1 pause
