@echo off
title Video Downloader
python main.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Program exited with an error.
    pause
)

