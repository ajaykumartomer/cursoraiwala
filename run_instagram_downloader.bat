@echo off
cd /d "%~dp0"
echo ===========================================
echo  Instagram Archiver - Cookie Scan Download
echo  Order: Firefox -^> Chrome -^> Edge -^> Brave
echo ===========================================
python ig_archiver.py %*
if errorlevel 1 pause
