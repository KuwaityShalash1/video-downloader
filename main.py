"""
Video Downloader — A modern CLI tool for downloading videos and audio using yt-dlp.

Features:
  - Video + audio (merged high-definition)
  - Audio-only extraction (MP3 with customizable bitrate)
  - Video-only (no audio stream)
  - Interactive resolution and quality selection
  - Automatic Node.js runtime challenge solver (n-sig)
  - Seamless cookie authentication for age-restricted / private content
"""

import os
import sys
import shutil
from pathlib import Path

# ── Ensure PATH has tools like FFmpeg on Windows ─────────────────────────────
if sys.platform == "win32":
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment") as key:
            user_path, _ = winreg.QueryValueEx(key, "Path")
            if user_path:
                os.environ["PATH"] = user_path + ";" + os.environ.get("PATH", "")
    except Exception:
        pass

try:
    import yt_dlp
except ImportError:
    print("Error: yt-dlp is not installed.")
    print("Install it with:  pip install -r requirements.txt")
    input("\nPress Enter to exit...")
    sys.exit(1)

# ── Paths & Configuration ───────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent
DOWNLOAD_DIR = PROJECT_ROOT / "downloads"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Look for cookies.txt in project root first, then fallback to global Downloads
COOKIES_FILE = PROJECT_ROOT / "cookies.txt"
if not COOKIES_FILE.is_file():
    alt_cookie = Path.home() / "Downloads" / "VideoDownloader" / "cookies.txt"
    if alt_cookie.is_file():
        COOKIES_FILE = alt_cookie

MODES = {
    "1": "Video + Audio",
    "2": "Audio only (MP3)",
    "3": "Video only (no audio)",
}

AUDIO_BITRATES = {
    "1": ("320", "320 kbps (highest)"),
    "2": ("256", "256 kbps"),
    "3": ("192", "192 kbps"),
    "4": ("128", "128 kbps (smallest)"),
}


# ── Helpers ──────────────────────────────────────────────────────────────────
def _pause_and_exit(code: int = 1) -> None:
    """Keep console window open before exit."""
    input("\nPress Enter to exit...")
    sys.exit(code)


def _banner() -> None:
    """Print the startup banner."""
    width = 46
    print()
    print("═" * width)
    print("  🎬  VIDEO DOWNLOADER".center(width))
    print("═" * width)
    print()


def _require_ffmpeg() -> bool:
    """Return True if FFmpeg is available, otherwise print setup instructions."""
    if shutil.which("ffmpeg") is not None:
        return True
    print("\n⚠  FFmpeg is not installed or not found in PATH.")
    print("   It is required to merge video+audio and convert audio to MP3.")
    print("   Windows: winget install Gyan.FFmpeg.Essentials")
    print("   macOS:   brew install ffmpeg")
    print("   Linux:   sudo apt install ffmpeg")
    return False


def _base_ydl_opts(use_cookies: bool = True) -> dict:
    """Return base yt-dlp options shared across operations."""
    opts: dict = {
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        # Node.js challenge solver for YouTube's n-sig cipher
        "js_runtimes": {"node": {}},
    }
    if use_cookies and COOKIES_FILE.is_file():
        opts["cookiefile"] = str(COOKIES_FILE)
    return opts


def _prompt_choice(prompt: str, valid: set[str]) -> str | None:
    """Prompt the user for a selection from valid choices."""
    choice = input(prompt).strip()
    if choice in valid:
        return choice
    print("Invalid selection.")
    return None


def choose_resolution(heights: list[int]) -> int | None:
    """Prompt user to choose video resolution from available streams."""
    if not heights:
        print("  No resolution info available — defaulting to best quality.")
        return None

    print("\nAvailable resolutions:")
    print("  0 — Best available")
    for i, h in enumerate(heights, start=1):
        print(f"  {i} — {h}p")

    while True:
        raw = input("Your choice: ").strip()
        if raw == "0":
            return None
        if raw.isdigit() and 1 <= int(raw) <= len(heights):
            return heights[int(raw) - 1]
        print("Invalid choice, try again.")


def choose_audio_quality() -> str | None:
    """Prompt user to choose MP3 bitrate."""
    print("\nSelect audio quality:")
    for key, (_, label) in AUDIO_BITRATES.items():
        print(f"  {key} — {label}")

    choice = _prompt_choice("Your choice: ", set(AUDIO_BITRATES))
    if choice is None:
        return None
    return AUDIO_BITRATES[choice][0]


def _fetch_video_info(url: str) -> tuple[dict, bool] | tuple[None, bool]:
    """Extract metadata without downloading."""
    print("\nFetching video info...")

    cookie_attempts = [True] if COOKIES_FILE.is_file() else [False, True]

    for use_cookies in cookie_attempts:
        try:
            opts = _base_ydl_opts(use_cookies=use_cookies)
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)

            title = info.get("title", "Unknown")
            duration = info.get("duration")
            dur_str = f" ({duration // 60}m {duration % 60}s)" if duration else ""
            print(f"  Title : {title}{dur_str}")
            print(f"  Source: {info.get('extractor', 'unknown')}")
            return info, use_cookies

        except yt_dlp.utils.DownloadError as exc:
            err_msg = str(exc)
            is_restricted = any(kw in err_msg for kw in ("Sign in", "age", "confirm"))

            if not use_cookies and is_restricted:
                if COOKIES_FILE.is_file():
                    print("  Video is age-restricted, retrying with cookies.txt...")
                    continue
                else:
                    _print_cookie_instructions()
                    return None, False

            print(f"\n❌  Could not fetch video info.\n")
            if is_restricted:
                print("   Reason: This video is age-restricted.")
                print("   Your cookies.txt may be expired or missing.")
                _print_cookie_instructions()
            elif "Private video" in err_msg:
                print("   Reason: This video is private.")
            elif "Video unavailable" in err_msg:
                print("   Reason: This video is unavailable or has been removed.")
            else:
                print(f"   {err_msg}")
            return None, False

        except Exception as exc:
            print(f"\n❌  Unexpected error:\n   {exc}")
            return None, False

    return None, False


def _print_cookie_instructions() -> None:
    """Print step-by-step instructions for exporting cookies."""
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║  This video is age-restricted and requires YouTube cookies. ║
╚══════════════════════════════════════════════════════════════╝

  Setup instructions:
  1. Install "Get cookies.txt LOCALLY" extension in Chrome/Edge/Firefox:
     https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc

  2. Go to youtube.com and ensure you are logged in.
  3. Click extension → Export → Save as:
     {COOKIES_FILE}

  4. Run this program again!
""")


def _available_heights(info: dict) -> list[int]:
    """Return sorted unique video heights."""
    return sorted(
        {
            f["height"]
            for f in info.get("formats", [])
            if f.get("vcodec") not in (None, "none")
            and isinstance(f.get("height"), int)
        },
        reverse=True,
    )


def _build_options(mode: str, info: dict, use_cookies: bool = True) -> dict | None:
    """Build yt-dlp download options for selected mode."""
    options = _base_ydl_opts(use_cookies=use_cookies)
    options.update({
        "outtmpl": str(DOWNLOAD_DIR / "%(title).200s.%(ext)s"),
        "windowsfilenames": True,
        "quiet": False,
        "no_warnings": True,
    })

    if mode in ("1", "3"):
        heights = _available_heights(info)
        quality = choose_resolution(heights)
        h_filter = f"[height<={quality}]" if quality else ""

        if mode == "1":
            options["format"] = f"bestvideo{h_filter}+bestaudio/best{h_filter}"
        else:
            options["format"] = f"bestvideo{h_filter}"

    elif mode == "2":
        bitrate = choose_audio_quality()
        if bitrate is None:
            return None
        options["format"] = "bestaudio/best"
        options["postprocessors"] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": bitrate,
            }
        ]

    return options


# ── Main ─────────────────────────────────────────────────────────────────────
def main() -> None:
    _banner()

    # Show cookies status
    if COOKIES_FILE.is_file():
        print(f"  🍪 Cookies loaded: {COOKIES_FILE.name}")
    else:
        print(f"  ℹ  No cookies.txt found (only needed for age-restricted videos)")

    url = input("\nEnter video URL: ").strip()
    if not url:
        print("No URL provided.")
        _pause_and_exit()

    # --- Select download mode ---
    print("\nDownload mode:")
    for key, label in MODES.items():
        print(f"  {key} — {label}")

    mode = _prompt_choice("Your choice: ", set(MODES))
    if mode is None:
        _pause_and_exit()

    # --- FFmpeg check ---
    if mode in ("1", "2") and not _require_ffmpeg():
        _pause_and_exit()

    # --- Fetch metadata ---
    result, used_cookies = _fetch_video_info(url)
    if result is None:
        _pause_and_exit()
    info = result

    # --- Build options ---
    options = _build_options(mode, info, use_cookies=used_cookies)
    if options is None:
        _pause_and_exit()

    # --- Download ---
    print(f"\nStarting download...")
    print(f"  Destination: {DOWNLOAD_DIR}\n")

    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            ydl.download([url])
        print(f"\n✅ Done! File saved to:\n  {DOWNLOAD_DIR}")
    except Exception as exc:
        print(f"\n❌ Download failed:\n  {exc}")

    input("\nPress Enter to exit...")


if __name__ == "__main__":
    main()
