"""
Video & Audio Downloader — A modern, full-featured CLI tool powered by yt-dlp.

Features:
  - Video + Audio merging (always outputs universal MP4)
  - Audio extraction to MP3 with album art & metadata tagging
  - Video-only downloads
  - Automatic clipboard URL detection
  - Playlist detection (choose single item or entire playlist)
  - Automatic Node.js challenge solving for YouTube n-sig cipher
  - Seamless cookie authentication for age-restricted content
  - Post-download options (download another, open destination folder)
"""

import os
import sys
import shutil
import urllib.parse
from pathlib import Path

# ── Windows PATH Hotfix (ensures FFmpeg is detected without reboot) ───────────
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
    print("Run: pip install -r requirements.txt")
    input("\nPress Enter to exit...")
    sys.exit(1)

# ── Paths & Configuration ───────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent
DOWNLOAD_DIR = PROJECT_ROOT / "downloads"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Cookie resolution: check project folder first, then global downloads
COOKIES_FILE = PROJECT_ROOT / "cookies.txt"
if not COOKIES_FILE.is_file():
    alt_cookie = Path.home() / "Downloads" / "VideoDownloader" / "cookies.txt"
    if alt_cookie.is_file():
        COOKIES_FILE = alt_cookie

MODES = {
    "1": "Video + Audio  (Standard MP4)",
    "2": "Audio only     (MP3 with Album Art)",
    "3": "Video only     (No Audio)",
}

AUDIO_BITRATES = {
    "1": ("320", "320 kbps (High Fidelity)"),
    "2": ("256", "256 kbps (Standard High)"),
    "3": ("192", "192 kbps (Balanced)"),
    "4": ("128", "128 kbps (Compact)"),
}


# ── UI & Helpers ─────────────────────────────────────────────────────────────
def _banner() -> None:
    """Display startup header."""
    width = 50
    print()
    print("═" * width)
    print("     🎬  VIDEO & AUDIO DOWNLOADER".center(width))
    print("═" * width)


def _get_clipboard_url() -> str | None:
    """Attempt to read a valid HTTP/HTTPS URL from clipboard."""
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        text = root.clipboard_get().strip()
        root.destroy()
        if text.startswith(("http://", "https://")):
            return text
    except Exception:
        pass
    return None


def _require_ffmpeg() -> bool:
    """Verify FFmpeg is present in PATH."""
    if shutil.which("ffmpeg") is not None:
        return True
    print("\n⚠  FFmpeg is required for merging formats and MP3 conversion.")
    print("   Install it using:")
    print("     Windows: winget install Gyan.FFmpeg.Essentials")
    print("     macOS:   brew install ffmpeg")
    print("     Linux:   sudo apt install ffmpeg")
    return False


def _base_ydl_opts(use_cookies: bool = True, noplaylist: bool = True) -> dict:
    """Return common base options for yt-dlp."""
    opts: dict = {
        "noplaylist": noplaylist,
        "quiet": True,
        "no_warnings": True,
        # Node.js runtime for solving YouTube signature cipher
        "js_runtimes": {"node": {}},
    }
    if use_cookies and COOKIES_FILE.is_file():
        opts["cookiefile"] = str(COOKIES_FILE)
    return opts


def _prompt_choice(prompt: str, valid: set[str], default: str | None = None) -> str | None:
    """Prompt user for a choice with an optional default."""
    raw = input(prompt).strip()
    if not raw and default:
        return default
    if raw in valid:
        return raw
    print("❌ Invalid selection.")
    return None


def _format_duration(seconds: int | float | None) -> str:
    """Format duration into HH:MM:SS or MM:SS."""
    if not seconds:
        return ""
    total = int(seconds)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def _check_playlist(url: str) -> tuple[str, bool]:
    """
    Detect if the URL belongs to a playlist.
    Returns (cleaned_url, is_playlist_mode).
    """
    parsed = urllib.parse.urlparse(url)
    params = urllib.parse.parse_qs(parsed.query)

    if "list" in params and "watch" in parsed.path:
        # Link has both a video and a playlist
        print("\nℹ  This URL is part of a playlist:")
        print("  1 — Download this single video only (Recommended)")
        print("  2 — Download the entire playlist")
        choice = _prompt_choice("Your choice [1]: ", {"1", "2"}, default="1")
        if choice == "2":
            return url, False  # Keep playlist active (noplaylist=False)
        else:
            # Strip playlist params to guarantee single video download
            params.pop("list", None)
            params.pop("index", None)
            new_query = urllib.parse.urlencode(params, doseq=True)
            cleaned_url = urllib.parse.urlunparse(parsed._replace(query=new_query))
            return cleaned_url, True

    return url, True


# ── Metadata & Quality Selection ─────────────────────────────────────────────
def _fetch_video_info(url: str, noplaylist: bool = True) -> tuple[dict, bool] | tuple[None, bool]:
    """Fetch video metadata with cookie retry logic."""
    print("\n⏳ Fetching info from server...")

    cookie_attempts = [True] if COOKIES_FILE.is_file() else [False, True]

    for use_cookies in cookie_attempts:
        try:
            opts = _base_ydl_opts(use_cookies=use_cookies, noplaylist=noplaylist)
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)

            title = info.get("title", "Unknown")
            uploader = info.get("uploader") or info.get("channel") or ""
            duration = _format_duration(info.get("duration"))
            uploader_str = f" • {uploader}" if uploader else ""
            dur_str = f" [{duration}]" if duration else ""

            print(f"\n  🎯 Title   : {title}{dur_str}")
            if uploader_str:
                print(f"  👤 Channel : {uploader}")
            return info, use_cookies

        except yt_dlp.utils.DownloadError as exc:
            err_msg = str(exc)
            is_restricted = any(kw in err_msg for kw in ("Sign in", "age", "confirm"))

            if not use_cookies and is_restricted:
                if COOKIES_FILE.is_file():
                    print("  🔒 Video is restricted, applying cookies.txt...")
                    continue
                else:
                    _print_cookie_instructions()
                    return None, False

            print(f"\n❌ Error fetching info:")
            if is_restricted:
                print("   Reason: This content is age-restricted or requires login.")
                print("   Your cookies.txt may be expired or missing.")
                _print_cookie_instructions()
            elif "Private video" in err_msg:
                print("   Reason: This video is private.")
            elif "Video unavailable" in err_msg:
                print("   Reason: Video is unavailable or has been removed.")
            else:
                print(f"   {err_msg}")
            return None, False

        except Exception as exc:
            print(f"\n❌ Unexpected error:\n   {exc}")
            return None, False

    return None, False


def _print_cookie_instructions() -> None:
    """Print step-by-step instructions for exporting cookies."""
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║  This video requires authentication (Age-Gated / Private)   ║
╚══════════════════════════════════════════════════════════════╝

  How to authenticate:
  1. Install browser extension "Get cookies.txt LOCALLY":
     https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc
  2. Sign in to youtube.com in your browser.
  3. Click extension → Export → Save as:
     {COOKIES_FILE}
  4. Run this script again!
""")


def choose_resolution(heights: list[int]) -> int | None:
    """Interactive resolution picker."""
    if not heights:
        print("  ℹ  Stream list has no height tags — defaulting to best quality.")
        return None

    print("\nSelect resolution:")
    print("  0 — Best available (Default)")
    for i, h in enumerate(heights, start=1):
        print(f"  {i} — {h}p")

    while True:
        raw = input("Your choice [0]: ").strip()
        if not raw or raw == "0":
            return None
        if raw.isdigit() and 1 <= int(raw) <= len(heights):
            return heights[int(raw) - 1]
        print("❌ Invalid choice, please try again.")


def choose_audio_quality() -> str | None:
    """Interactive audio bitrate picker."""
    print("\nSelect MP3 quality:")
    for key, (_, label) in AUDIO_BITRATES.items():
        print(f"  {key} — {label}")

    choice = _prompt_choice("Your choice [1]: ", set(AUDIO_BITRATES), default="1")
    if choice is None:
        return None
    return AUDIO_BITRATES[choice][0]


def _available_heights(info: dict) -> list[int]:
    """Extract and sort unique video heights."""
    return sorted(
        {
            f["height"]
            for f in info.get("formats", [])
            if f.get("vcodec") not in (None, "none")
            and isinstance(f.get("height"), int)
        },
        reverse=True,
    )


# ── Option Builder ───────────────────────────────────────────────────────────
def _build_options(
    mode: str,
    info: dict,
    use_cookies: bool = True,
    noplaylist: bool = True
) -> dict | None:
    """Assemble the yt-dlp download options dictionary."""
    options = _base_ydl_opts(use_cookies=use_cookies, noplaylist=noplaylist)
    options.update({
        "outtmpl": str(DOWNLOAD_DIR / "%(title).200s.%(ext)s"),
        "windowsfilenames": True,
        "quiet": False,
        "no_warnings": True,
    })

    if mode == "1":
        # Video + Audio merged into universal MP4
        heights = _available_heights(info)
        quality = choose_resolution(heights)
        h_filter = f"[height<={quality}]" if quality else ""

        options["format"] = f"bestvideo{h_filter}+bestaudio/best{h_filter}"
        options["merge_output_format"] = "mp4"

    elif mode == "2":
        # Audio only (MP3) with thumbnail & metadata embedding
        bitrate = choose_audio_quality()
        if bitrate is None:
            return None

        options["format"] = "bestaudio/best"
        options["writethumbnail"] = True
        options["postprocessors"] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": bitrate,
            },
            {
                "key": "FFmpegMetadata",
                "add_metadata": True,
            },
            {
                "key": "EmbedThumbnail",
                "already_have_thumbnail": False,
            },
        ]

    elif mode == "3":
        # Video only (no audio)
        heights = _available_heights(info)
        quality = choose_resolution(heights)
        h_filter = f"[height<={quality}]" if quality else ""
        options["format"] = f"bestvideo{h_filter}"

    return options


# ── Execution Loop ───────────────────────────────────────────────────────────
def run_downloader() -> None:
    """Execute a single download workflow."""
    _banner()

    # Show cookies status
    if COOKIES_FILE.is_file():
        print(f"  🍪 Cookie file active: {COOKIES_FILE.name}")
    else:
        print(f"  ℹ  No cookies.txt (only needed for age-restricted videos)")

    # Clipboard detection
    clip_url = _get_clipboard_url()
    if clip_url:
        print(f"\n📋 Clipboard URL detected:\n   {clip_url}")
        prompt_text = "Press Enter to use this URL, or paste another: "
    else:
        prompt_text = "\nEnter video URL: "

    raw_url = input(prompt_text).strip()
    target_url = raw_url if raw_url else (clip_url or "")

    if not target_url:
        print("❌ No URL provided.")
        return

    # Check for playlist parameters
    cleaned_url, noplaylist = _check_playlist(target_url)

    # Mode selection
    print("\nDownload Mode:")
    for key, label in MODES.items():
        print(f"  {key} — {label}")

    mode = _prompt_choice("Your choice [1]: ", set(MODES), default="1")
    if mode is None:
        return

    # FFmpeg verification for merge/MP3
    if mode in ("1", "2") and not _require_ffmpeg():
        return

    # Metadata extraction
    info, used_cookies = _fetch_video_info(cleaned_url, noplaylist=noplaylist)
    if info is None:
        return

    # Build options
    options = _build_options(mode, info, use_cookies=used_cookies, noplaylist=noplaylist)
    if options is None:
        return

    # Download
    print(f"\n🚀 Starting download...")
    print(f"  📁 Destination: {DOWNLOAD_DIR}\n")

    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            ydl.download([cleaned_url])
        print(f"\n🎉 Done! All files saved in:\n   {DOWNLOAD_DIR}")
    except Exception as exc:
        print(f"\n❌ Download failed:\n   {exc}")


def main() -> None:
    """Main application loop."""
    while True:
        run_downloader()

        print("\n" + "─" * 50)
        again = input("🔄 Download another video? (y/n) [n]: ").strip().lower()
        if again not in ("y", "yes"):
            break

    # Offer to open the downloads folder on Windows
    if sys.platform == "win32" and DOWNLOAD_DIR.is_dir():
        open_folder = input("\n📂 Open downloads folder? (y/n) [y]: ").strip().lower()
        if open_folder in ("", "y", "yes"):
            try:
                os.startfile(DOWNLOAD_DIR)
            except Exception:
                pass

    print("\nGoodbye! 👋")


if __name__ == "__main__":
    main()
