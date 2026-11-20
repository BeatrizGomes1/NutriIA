@echo off
rem Abre o iniciar.ps1 sem esbarrar na política de execução de scripts do Windows.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0iniciar.ps1"
pause
