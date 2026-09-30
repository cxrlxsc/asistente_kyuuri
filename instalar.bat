@echo off
REM Instalador de Kyuuri para Windows. Doble clic y listo.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0instalar.ps1"
echo.
pause
