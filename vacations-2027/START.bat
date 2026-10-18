@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title Vacations 2027 v1.0.2
if not exist "%~dp0runtime\python.exe" (
    echo Python runtime was not found. Extract the entire ZIP archive first.
    echo Do not launch START.bat directly from inside the ZIP.
    pause
    exit /b 1
)
"%~dp0runtime\python.exe" -I -X utf8 "%~dp0run_local.py" %*
if errorlevel 1 (
    echo.
    echo The program could not start. See the error message above.
    pause
    exit /b 1
)
endlocal
