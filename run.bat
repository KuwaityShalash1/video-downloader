@echo off
setlocal
title Video Downloader
cd /d "%~dp0"

where python >nul 2>&1
if errorlevel 1 (
    echo.
    echo Python was not found in PATH.
    echo Install it from https://www.python.org/downloads/ and tick "Add python.exe to PATH".
    echo.
    pause
    exit /b 1
)

python -c "import yt_dlp" >nul 2>&1
if errorlevel 1 (
    echo Installing dependencies...
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo Dependency installation failed.
        pause
        exit /b 1
    )
)

where ffmpeg >nul 2>&1
if errorlevel 1 (
    echo.
    echo WARNING: FFmpeg was not found. Merging and MP3 conversion will fail.
    echo Install it with: winget install Gyan.FFmpeg.Essentials
    echo.
)

python main.py %*
if errorlevel 1 (
    echo.
    echo Program exited with an error.
    pause
)
endlocal
