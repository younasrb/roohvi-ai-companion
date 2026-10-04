@echo off
setlocal
cd /d "%~dp0"
title Roohvi

rem --- 1. Virtual environment (Python 3.11 - 3.13 preferred) ---
if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    py -3.12 -m venv .venv >nul 2>&1
    if errorlevel 1 py -3.13 -m venv .venv >nul 2>&1
    if errorlevel 1 py -3.11 -m venv .venv >nul 2>&1
    if errorlevel 1 python -m venv .venv
    if errorlevel 1 (
        echo.
        echo Python nahi mila. python.org se Python 3.12 install karein - "Add python.exe to PATH" tick karna na bhoolein.
        pause
        exit /b 1
    )
)

rem --- 2. Install dependencies once ---
if not exist ".venv\.deps_installed" (
    echo Installing dependencies - pehli dafa kuch minute lagenge...
    ".venv\Scripts\python.exe" setup.py
    if errorlevel 1 (
        echo.
        echo Setup fail hua. Upar wala error message dekhein.
        pause
        exit /b 1
    )
    echo ok> ".venv\.deps_installed"
)

rem --- 2b. 3D avatar support (optional; also upgrades older installs) ---
".venv\Scripts\python.exe" -c "import PyQt6.QtWebEngineWidgets" >nul 2>&1
if errorlevel 1 (
    echo Installing 3D avatar support - ek dafa...
    ".venv\Scripts\python.exe" -m pip install "PyQt6-WebEngine>=6.6,<7"
)

rem --- 3. Run ---
".venv\Scripts\python.exe" main.py
if errorlevel 1 pause
