@echo off
title DIXII - AI Document Processor

echo.
echo ===============================================
echo 🏛️  DIXII - AI Tax Document Processing System
echo ===============================================
echo.

echo 📦 Installing required AI tools...
echo This may take a few minutes on first run...
echo.

pip install -r requirements.txt

if %errorlevel% neq 0 (
    echo.
    echo ❌ Installation failed. Trying alternative method...
    python -m pip install -r requirements.txt
)

if %errorlevel% neq 0 (
    echo.
    echo ❌ Could not install dependencies. Please check:
    echo    1. Python is installed with "Add to PATH" checked
    echo    2. You have internet connection
    echo    3. Try running as Administrator
    echo.
    pause
    exit /b 1
)

echo.
echo ✅ Installation complete!
echo.
echo 🚀 Starting DIXII...
echo.
echo Once started, open your browser to: http://localhost:8080
echo.
echo ⚠️  Keep this window open while using DIXII
echo    Close this window to stop DIXII
echo.

python run.py

if %errorlevel% neq 0 (
    echo.
    echo ❌ Failed to start DIXII. Please check the error above.
    echo.
    pause
) 