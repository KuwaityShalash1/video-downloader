#!/usr/bin/env bash
# Launcher for macOS and Linux. Passes every argument through to main.py.
set -euo pipefail
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
    echo "Python 3 is not installed. Get it from https://www.python.org/downloads/" >&2
    exit 1
fi

# Use a local virtualenv when one exists.
if [ -f .venv/bin/activate ]; then
    # shellcheck disable=SC1091
    source .venv/bin/activate
fi

if ! python3 -c "import yt_dlp" >/dev/null 2>&1; then
    echo "yt-dlp is missing. Installing requirements..."
    python3 -m pip install -r requirements.txt
fi

if ! command -v ffmpeg >/dev/null 2>&1; then
    echo "⚠  FFmpeg not found: merging and audio conversion will fail." >&2
    echo "   macOS: brew install ffmpeg | Linux: sudo apt install ffmpeg" >&2
fi

exec python3 main.py "$@"
