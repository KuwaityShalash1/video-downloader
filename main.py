"""
Video & Audio Downloader — A modern, full-featured CLI tool powered by yt-dlp.

Features:
  - Video + Audio merging (always outputs universal MP4)
  - Audio extraction to MP3 with album art & metadata tagging (or keep the original stream)
  - Video-only downloads
  - Automatic clipboard URL detection
  - Playlist detection (choose single item or entire playlist)
  - Automatic Node.js challenge solving for YouTube n-sig cipher
  - Seamless cookie authentication (cookies.txt, --cookies-from-browser)
  - Resumable downloads, retries, and skipping of already-downloaded media
  - Scriptable, non-interactive mode via command-line flags
"""

from __future__ import annotations

import argparse
import contextlib
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path
from typing import Any, NamedTuple

APP_NAME = "Video & Audio Downloader"
VERSION = "2.0.0"

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


def _load_yt_dlp():
    """Import yt-dlp lazily so `--doctor` works even when it is missing."""
    try:
        import yt_dlp  # noqa: PLC0415

        return yt_dlp
    except ImportError:
        return None


yt_dlp = _load_yt_dlp()

# ── Paths & Configuration ───────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_DOWNLOAD_DIR = PROJECT_ROOT / "downloads"

# Destination: --output flag > VD_OUTPUT_DIR env var > ./downloads
DOWNLOAD_DIR = Path(os.environ.get("VD_OUTPUT_DIR") or DEFAULT_DOWNLOAD_DIR).expanduser()

# Cookies: --cookies flag > VD_COOKIES env var > ./cookies.txt
COOKIES_FILE = Path(os.environ.get("VD_COOKIES") or (PROJECT_ROOT / "cookies.txt")).expanduser()

# Remembers downloaded media so it is never fetched twice (--no-archive disables it)
ARCHIVE_FILE = PROJECT_ROOT / ".download-archive.txt"

MODES = {
    "1": ("video", "Video + Audio  (Standard MP4)"),
    "2": ("audio", "Audio only     (MP3 with Album Art)"),
    "3": ("video-only", "Video only     (No Audio)"),
}

MODE_CHOICES = ("video", "audio", "video-only")

MODE_ALIASES = {
    "video": "video",
    "video+audio": "video",
    "1": "video",
    "audio": "audio",
    "mp3": "audio",
    "2": "audio",
    "video-only": "video-only",
    "video_only": "video-only",
    "videoonly": "video-only",
    "3": "video-only",
}

AUDIO_BITRATES = {
    "1": ("320", "320 kbps (High Fidelity)"),
    "2": ("256", "256 kbps (Standard High)"),
    "3": ("192", "192 kbps (Balanced)"),
    "4": ("128", "128 kbps (Compact)"),
}

AUDIO_FORMATS = {
    "1": ("mp3", "MP3  (converted with album art)"),
    "2": ("original", "Keep original stream (m4a/opus, no re-encode)"),
}

SUPPORTED_BROWSERS = {
    "brave",
    "chrome",
    "chromium",
    "edge",
    "firefox",
    "opera",
    "safari",
    "vivaldi",
    "whale",
}

# Query-string keys that turn a single video link into a playlist link.
PLAYLIST_PARAM_KEYS = ("list", "index", "start_radio", "playnext")

_last_progress_ts = 0.0
_downloaded_something = False


# ── UI & Helpers ─────────────────────────────────────────────────────────────
def _banner() -> None:
    """Display startup header."""
    width = 50
    print()
    print("═" * width)
    print("     🎬  VIDEO & AUDIO DOWNLOADER".center(width))
    print("═" * width)


def _stdin_is_tty() -> bool:
    try:
        return sys.stdin is not None and sys.stdin.isatty()
    except Exception:
        return False


def _stdout_is_tty() -> bool:
    try:
        return sys.stdout is not None and sys.stdout.isatty()
    except Exception:
        return False


def _prompt_choice(
    prompt: str, valid: set[str] | dict[str, Any], default: str | None = None
) -> str:
    """Prompt until the user picks a valid option (never returns None)."""
    options = "/".join(sorted(str(k) for k in valid))
    while True:
        try:
            raw = input(prompt).strip().lower()
        except EOFError:
            print()
            raise
        if not raw:
            if default is not None:
                return default
            print(f"❌ Please choose one of: {options}")
            continue
        if raw in valid:
            return raw
        print(f"❌ Invalid selection. Choose one of: {options}")


def _prompt_yes_no(prompt: str, default: bool = True) -> bool:
    """Prompt for a yes/no answer, defaulting on empty input."""
    suffix = "[Y/n]" if default else "[y/N]"
    while True:
        try:
            raw = input(f"{prompt} {suffix}: ").strip().lower()
        except EOFError:
            print()
            raise
        if not raw:
            return default
        if raw in ("y", "yes"):
            return True
        if raw in ("n", "no"):
            return False
        print("❌ Please answer y or n.")


def normalize_url(raw: str | None) -> str | None:
    """Return a cleaned http(s) URL, or None when the input is not a URL."""
    if not raw:
        return None
    candidate = raw.strip().strip("\"'<>").strip()
    if not candidate:
        return None
    parsed = urllib.parse.urlparse(candidate)
    if parsed.scheme not in ("http", "https"):
        return None
    if not parsed.netloc or "." not in parsed.netloc:
        return None
    return candidate


def _clipboard_text() -> str | None:
    """Read raw text from the system clipboard using the cheapest available method."""
    commands: list[list[str]] = []
    if sys.platform == "win32":
        commands.append(["powershell", "-NoProfile", "-Command", "Get-Clipboard"])
    elif sys.platform == "darwin":
        commands.append(["pbpaste"])
    else:
        commands.extend(
            [
                ["wl-paste", "--no-newline"],
                ["xclip", "-selection", "clipboard", "-o"],
                ["xsel", "--clipboard", "--output"],
            ]
        )

    for cmd in commands:
        if shutil.which(cmd[0]) is None:
            continue
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=3, check=False)
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except Exception:
            continue

    # tkinter is available on most desktop Python installs but needs a display.
    try:
        import tkinter as tk

        root = tk.Tk()
        root.withdraw()
        try:
            text = root.clipboard_get().strip()
        finally:
            root.destroy()
        if text:
            return text
    except Exception:
        pass

    try:
        import pyperclip  # type: ignore[import-not-found]

        text = pyperclip.paste().strip()
        if text:
            return text
    except Exception:
        pass

    return None


def _get_clipboard_url() -> str | None:
    """Attempt to read a valid HTTP/HTTPS URL from clipboard."""
    return normalize_url(_clipboard_text())


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


def _format_bytes(num: int | float | None) -> str:
    """Human readable byte size."""
    if not num or num < 0:
        return "?"
    units = ["B", "KiB", "MiB", "GiB", "TiB"]
    value = float(num)
    index = 0
    while value >= 1024 and index < len(units) - 1:
        value /= 1024
        index += 1
    if index == 0:
        return f"{int(value)} B"
    return f"{value:.2f} {units[index]}"


def parse_height(value: str | int | None) -> int | None:
    """Parse a quality value such as '1080', '720p' or 'best' into a height."""
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in ("", "0", "best", "max", "auto", "any"):
        return None
    match = re.fullmatch(r"(\d{3,4})p?", text)
    if not match:
        return None
    return int(match.group(1))


# ── URL & Playlist Analysis ─────────────────────────────────────────────────
class UrlInfo(NamedTuple):
    """Parsed view of a user supplied link."""

    url: str
    has_playlist: bool
    has_video: bool


def analyze_url(url: str) -> UrlInfo:
    """Split a URL into its single-video form and playlist/video markers."""
    parsed = urllib.parse.urlparse(url)
    params = urllib.parse.parse_qs(parsed.query)

    has_playlist = bool(params.get("list"))
    has_video = (
        bool(params.get("v"))
        or any(segment in parsed.path for segment in ("/shorts/", "/live/", "/embed/", "/v/"))
        or (parsed.netloc.endswith("youtu.be") and parsed.path.strip("/") != "")
    )

    cleaned = dict(params)
    for key in PLAYLIST_PARAM_KEYS:
        cleaned.pop(key, None)

    single_url = urllib.parse.urlunparse(
        parsed._replace(query=urllib.parse.urlencode(cleaned, doseq=True))
    )
    return UrlInfo(url=single_url, has_playlist=has_playlist, has_video=has_video)


def resolve_target(url: str, playlist_flag: bool | None, interactive: bool) -> tuple[str, bool]:
    """
    Decide which URL to download and whether playlists are disabled.

    Returns (url_to_download, noplaylist).
    """
    info = analyze_url(url)

    if not info.has_playlist:
        return url, True

    if playlist_flag is True:
        return url, False

    if playlist_flag is False:
        return info.url, True

    # The link is a pure playlist (no single video attached): playlists are the only option.
    if not info.has_video:
        print("\nℹ  This link points to a playlist — the whole playlist will be downloaded.")
        return url, False

    if not interactive:
        return info.url, True

    print("\nℹ  This URL is part of a playlist:")
    print("  1 — Download this single video only (Recommended)")
    print("  2 — Download the entire playlist")
    choice = _prompt_choice("Your choice [1]: ", {"1", "2"}, default="1")
    if choice == "2":
        return url, False
    return info.url, True


# ── Metadata & Quality Selection ─────────────────────────────────────────────
def _available_heights(info: dict) -> list[int]:
    """Extract and sort unique video heights."""
    return sorted(
        {
            fmt["height"]
            for fmt in (info.get("formats") or [])
            if fmt.get("vcodec") not in (None, "none") and isinstance(fmt.get("height"), int)
        },
        reverse=True,
    )


def _stream_size(fmt: dict) -> int:
    size = fmt.get("filesize") or fmt.get("filesize_approx")
    return int(size) if size else 0


def estimate_size(info: dict, mode: str, height: int | None = None) -> int | None:
    """Rough download size in bytes for the selected mode, or None if unknown."""
    formats = info.get("formats") or []
    videos = [
        fmt
        for fmt in formats
        if fmt.get("vcodec") not in (None, "none") and isinstance(fmt.get("height"), int)
    ]
    audios = [
        fmt
        for fmt in formats
        if fmt.get("acodec") not in (None, "none") and fmt.get("vcodec") in (None, "none")
    ]

    if height:
        limited = [fmt for fmt in videos if fmt["height"] <= height]
        videos = limited or videos

    best_video = max(videos, key=lambda f: (f["height"], f.get("tbr") or 0), default=None)
    best_audio = max(audios, key=lambda f: (f.get("abr") or 0, f.get("tbr") or 0), default=None)

    total = 0
    if mode in ("video", "video-only") and best_video is not None:
        total += _stream_size(best_video)
    if mode in ("video", "audio") and best_audio is not None:
        total += _stream_size(best_audio)
    return total or None


def choose_resolution(heights: list[int], requested: str | int | None = None) -> int | None:
    """Interactive resolution picker (returns None for 'best')."""
    if requested is not None:
        parsed = parse_height(requested)
        if parsed is None:
            return None
        if heights and parsed not in heights:
            print(f"  ℹ  {parsed}p is not offered — using the closest available quality.")
        return parsed

    if not heights:
        print("  ℹ  Stream list has no height tags — defaulting to best quality.")
        return None

    print("\nSelect resolution:")
    print("  0 — Best available (Default)")
    for index, value in enumerate(heights, start=1):
        print(f"  {index} — {value}p")

    while True:
        raw = input("Your choice [0]: ").strip().lower()
        if not raw or raw == "0":
            return None
        if raw.isdigit() and 1 <= int(raw) <= len(heights):
            return heights[int(raw) - 1]
        if parse_height(raw) is not None:
            return parse_height(raw)
        print("❌ Invalid choice, please try again.")


def choose_audio_quality() -> str:
    """Interactive audio bitrate picker."""
    print("\nSelect MP3 quality:")
    for key, (_, label) in AUDIO_BITRATES.items():
        print(f"  {key} — {label}")

    choice = _prompt_choice("Your choice [1]: ", set(AUDIO_BITRATES), default="1")
    return AUDIO_BITRATES[choice][0]


def choose_audio_format() -> str:
    """Interactive audio delivery picker (MP3 vs original stream)."""
    print("\nAudio output:")
    for key, (_, label) in AUDIO_FORMATS.items():
        print(f"  {key} — {label}")
    choice = _prompt_choice("Your choice [1]: ", set(AUDIO_FORMATS), default="1")
    return AUDIO_FORMATS[choice][0]


# ── Option Builder ───────────────────────────────────────────────────────────
def build_format_selector(mode: str, height: int | None) -> str:
    """Return the yt-dlp format expression for a mode and optional height cap."""
    height_filter = f"[height<={height}]" if height else ""
    if mode == "audio":
        return "bestaudio/best"
    if mode == "video-only":
        return f"bestvideo{height_filter}" if height else "bestvideo/best"
    if height:
        return f"bestvideo{height_filter}+bestaudio/best{height_filter}/best"
    return "bestvideo+bestaudio/best"


def build_audio_postprocessors(audio_format: str, bitrate: str) -> list[dict]:
    """Build the post-processor chain for audio downloads."""
    processors: list[dict] = [
        {"key": "FFmpegMetadata", "add_metadata": True},
        {"key": "EmbedThumbnail", "already_have_thumbnail": False},
    ]
    if audio_format == "mp3":
        processors.insert(
            0,
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": bitrate,
            },
        )
    return processors


def build_outtmpl(output_dir: Path, playlist: bool) -> str:
    """Output filename template, one folder per playlist."""
    if playlist:
        return str(
            output_dir
            / "%(playlist_title|Playlist).120s"
            / "%(playlist_index)03d - %(title).120s.%(ext)s"
        )
    return str(output_dir / "%(title).120s.%(ext)s")


def _progress_hook(data: dict) -> None:
    """Render a compact custom progress line while downloading."""
    global _last_progress_ts, _downloaded_something

    status = data.get("status")
    if status == "finished":
        _last_progress_ts = 0.0
        _downloaded_something = True
        if _stdout_is_tty():
            name = Path(data.get("filename") or "").name
            print("\r" + f"  ✅ Downloaded: {name}".ljust(78)[:78])
        return

    if status != "downloading" or not _stdout_is_tty():
        return

    now = time.monotonic()
    if now - _last_progress_ts < 0.15:
        return
    _last_progress_ts = now

    total = data.get("total_bytes") or data.get("total_bytes_estimate")
    done = data.get("downloaded_bytes") or 0
    if total:
        body = f"{done / total * 100:5.1f}%  {_format_bytes(done)} / {_format_bytes(total)}"
    else:
        body = f"       {_format_bytes(done)}"

    speed = (data.get("_speed_str") or "").strip()
    eta = (data.get("_eta_str") or "").strip()

    message = f"  ⬇  {body}"
    if speed and "unknown" not in speed.lower():
        message += f"  {speed}"
    if eta and "unknown" not in eta.lower() and eta.upper() != "N/A":
        message += f"  ETA {eta}"

    print("\r" + message.ljust(78)[:78], end="", flush=True)


def build_ydl_options(
    *,
    mode: str,
    output_dir: Path,
    height: int | None,
    bitrate: str,
    audio_format: str,
    playlist: bool,
    cookie_opts: dict,
    use_archive: bool,
    verbose: bool,
) -> dict:
    """Assemble the yt-dlp download options dictionary."""
    options: dict = {
        "noplaylist": not playlist,
        "quiet": not verbose,
        "no_warnings": not verbose,
        "noprogress": True,
        "js_runtimes": {"node": {}},
        # Reliability
        "retries": 10,
        "fragment_retries": 10,
        "socket_timeout": 30,
        "concurrent_fragment_downloads": 4,
        "continuedl": True,
        "outtmpl": build_outtmpl(output_dir, playlist),
        "windowsfilenames": True,
        "format": build_format_selector(mode, height),
        "progress_hooks": [_progress_hook],
    }

    if use_archive:
        options["download_archive"] = str(ARCHIVE_FILE)

    options.update(cookie_opts)

    if mode == "video":
        options["merge_output_format"] = "mp4"
    elif mode == "audio":
        options["writethumbnail"] = True
        options["postprocessors"] = build_audio_postprocessors(audio_format, bitrate)

    return options


# ── Network ─────────────────────────────────────────────────────────────────
def _parse_browser_spec(spec: str) -> tuple[str, str | None]:
    """Split 'chrome:Profile 1' into ('chrome', 'Profile 1')."""
    browser, _, profile = spec.strip().partition(":")
    return browser.strip().lower(), (profile.strip() or None)


def resolve_cookie_options(args: argparse.Namespace) -> dict:
    """Pick a single, well-defined cookie source."""
    if args.cookies:
        path = Path(args.cookies).expanduser()
        if path.is_file():
            return {"cookiefile": str(path)}
        print(f"⚠  Cookie file not found: {path}")
        return {}

    if args.cookies_from_browser:
        browser, profile = _parse_browser_spec(args.cookies_from_browser)
        if browser not in SUPPORTED_BROWSERS:
            print(f"⚠  '{browser}' is not a known browser — trying anyway.")
        return {"cookiesfrombrowser": (browser, profile, None, None)}

    if COOKIES_FILE.is_file():
        return {"cookiefile": str(COOKIES_FILE)}

    return {}


def _print_cookie_instructions() -> None:
    """Print step-by-step instructions for exporting cookies."""
    print(
        f"""
╔══════════════════════════════════════════════════════════════╗
║  This video requires authentication (Age-Gated / Private)   ║
╚══════════════════════════════════════════════════════════════╝

  Easiest fix — reuse your browser session:
    python main.py --cookies-from-browser chrome

  Or export a cookies file:
  1. Install browser extension "Get cookies.txt LOCALLY":
     https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc
  2. Sign in to youtube.com in your browser.
  3. Click extension → Export → Save as:
     {COOKIES_FILE}
  4. Run this script again!
"""
    )


def _describe_error(message: str) -> str:
    """Map a raw yt-dlp error message to a short human hint."""
    lowered = message.lower()
    if any(keyword in lowered for keyword in ("sign in", "age", "confirm", "login")):
        return "This content is age-restricted or requires login."
    if "private video" in lowered:
        return "This video is private."
    if "video unavailable" in lowered:
        return "Video is unavailable or has been removed."
    if "is not a valid url" in lowered:
        return "The URL is not valid."
    if "unsupported url" in lowered:
        return "This site is not supported by yt-dlp."
    return ""


def _primary_info(info: dict | None) -> dict:
    """Return the single-video info dict, drilling into playlists when needed."""
    if not info:
        return {}
    if info.get("_type") == "playlist":
        entries = info.get("entries") or []
        return entries[0] if entries else {}
    return info


def fetch_video_info(
    target_url: str,
    *,
    playlist: bool,
    cookie_opts: dict,
    verbose: bool,
) -> dict | None:
    """Fetch metadata for a video or playlist."""
    print("\n⏳ Fetching info from server...")

    options: dict = {
        "noplaylist": not playlist,
        "quiet": not verbose,
        "no_warnings": not verbose,
        "js_runtimes": {"node": {}},
    }
    options.update(cookie_opts)

    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(target_url, download=False)
    except yt_dlp.utils.DownloadError as exc:
        message = str(exc)
        hint = _describe_error(message)
        print("\n❌ Error fetching info:")
        if hint:
            print(f"   Reason: {hint}")
            if "restricted" in hint or "login" in hint:
                print("   Your cookies may be expired or missing.")
                _print_cookie_instructions()
        else:
            print(f"   {message}")
        return None
    except Exception as exc:  # noqa: BLE001 - surface any unexpected extractor failure
        print(f"\n❌ Unexpected error:\n   {exc}")
        return None

    if info is None:
        print("\n❌ No information returned for this URL.")
        return None

    if info.get("_type") == "playlist":
        count = info.get("playlist_count") or len(info.get("entries") or [])
        print(f"\n  📑 Playlist  : {info.get('title', 'Unknown')}")
        print(f"  🔢 Items     : {count}")

    primary = _primary_info(info)
    title = primary.get("title") or info.get("title") or "Unknown"
    uploader = primary.get("uploader") or primary.get("channel") or ""
    duration = _format_duration(primary.get("duration"))
    if info.get("_type") != "playlist":
        title_suffix = f" [{duration}]" if duration else ""
        print(f"\n  🎯 Title   : {title}{title_suffix}")
        if uploader:
            print(f"  👤 Channel : {uploader}")
    return info


# ── Doctor ──────────────────────────────────────────────────────────────────
def run_doctor() -> int:
    """Report environment health. Returns 0 when critical checks pass."""
    critical_ok = True
    print(f"\n{APP_NAME} — environment check\n")

    def report(label: str, ok: bool, detail: str, critical: bool = False) -> None:
        nonlocal critical_ok
        print(f"  {'✔' if ok else '✖'}  {label:<22} {detail}")
        if not ok and critical:
            critical_ok = False

    version = ".".join(str(part) for part in sys.version_info[:3])
    report("Python", sys.version_info >= (3, 10), f"{version} (need 3.10+)", critical=True)

    if yt_dlp is None:
        report("yt-dlp", False, "not installed — pip install -r requirements.txt", critical=True)
    else:
        report("yt-dlp", True, getattr(yt_dlp.version, "__version__", "installed"))

    ffmpeg = shutil.which("ffmpeg")
    report(
        "FFmpeg",
        ffmpeg is not None,
        ffmpeg or "missing — required to merge and convert",
        critical=True,
    )
    ffprobe = shutil.which("ffprobe")
    report("FFprobe", ffprobe is not None, ffprobe or "missing (optional)")

    node = shutil.which("node")
    report("Node.js", node is not None, node or "missing — recommended for YouTube cipher")

    report("Cookies file", COOKIES_FILE.is_file(), str(COOKIES_FILE))

    try:
        DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
        probe = DOWNLOAD_DIR / ".write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        writable, detail = True, str(DOWNLOAD_DIR)
    except Exception as exc:  # noqa: BLE001 - doctor must never crash
        writable, detail = False, f"{DOWNLOAD_DIR} ({exc})"
    report("Output folder", writable, detail, critical=True)

    print(
        "\n  Tip: pass --cookies-from-browser chrome to reuse your browser login"
        "\n       for age-restricted or member-only videos.\n"
    )
    return 0 if critical_ok else 1


# ── Execution Loop ───────────────────────────────────────────────────────────
def _resolve_mode(args: argparse.Namespace, interactive: bool) -> str | None:
    """Return the download mode, prompting when appropriate."""
    if args.mode:
        return MODE_ALIASES.get(args.mode)

    print("\nDownload Mode:")
    for key, (_, label) in MODES.items():
        print(f"  {key} — {label}")

    if not interactive:
        return "video"

    choice = _prompt_choice("Your choice [1]: ", set(MODES), default="1")
    return MODES[choice][0]


def _prompt_into_url(args: argparse.Namespace) -> str | None:
    """Ask for a URL, offering a clipboard URL when one is available."""
    clip_url = None if args.no_clipboard else _get_clipboard_url()
    if clip_url:
        print(f"\n📋 Clipboard URL detected:\n   {clip_url}")
        candidate = input("Press Enter to use this URL, or paste another: ").strip() or clip_url
    else:
        candidate = input("\nEnter video URL: ").strip()

    normalized = normalize_url(candidate)
    if normalized is None:
        print("❌ No valid URL provided.")
        return None
    return normalized


def download_once(args: argparse.Namespace, interactive: bool) -> bool:
    """Run a single download workflow. Returns True on success."""
    global _downloaded_something

    url = normalize_url(args.url)
    if args.url and url is None:
        print(f"❌ Not a valid URL: {args.url}")
        return False

    if url is None:
        if not interactive:
            print("❌ No URL provided.")
            return False
        url = _prompt_into_url(args)
        if url is None:
            return False

    target_url, noplaylist = resolve_target(url, args.playlist, interactive)
    playlist = not noplaylist

    mode = _resolve_mode(args, interactive)
    if mode not in MODE_CHOICES:
        print("❌ Unknown download mode.")
        return False

    if mode in ("video", "audio") and not _require_ffmpeg():
        return False

    bitrate = "320"
    audio_format = "mp3"
    if mode == "audio":
        if args.bitrate:
            bitrate = args.bitrate
        elif args.mode is None and interactive:
            bitrate = choose_audio_quality()

        if args.audio_format:
            audio_format = args.audio_format
        elif args.mode is None and interactive:
            audio_format = choose_audio_format()

    cookie_opts = resolve_cookie_options(args)
    output_dir = Path(args.output).expanduser() if args.output else DOWNLOAD_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    info = fetch_video_info(
        target_url, playlist=playlist, cookie_opts=cookie_opts, verbose=args.verbose
    )
    if info is None:
        return False

    primary = _primary_info(info)
    heights = _available_heights(primary)

    if mode in ("video", "video-only"):
        if args.quality:
            height = parse_height(args.quality)
            if height is None and args.quality.strip().lower() not in ("best", "0", "max"):
                print(f"⚠  Unrecognised quality '{args.quality}' — using best available.")
        elif args.mode is None and interactive:
            height = choose_resolution(heights)
        else:
            height = None
    else:
        height = None

    options = build_ydl_options(
        mode=mode,
        output_dir=output_dir,
        height=height,
        bitrate=bitrate,
        audio_format=audio_format,
        playlist=playlist,
        cookie_opts=cookie_opts,
        use_archive=args.archive,
        verbose=args.verbose,
    )

    size = estimate_size(primary, mode, height)
    print("\n🚀 Starting download...")
    print(f"  📁 Destination: {output_dir}")
    print(f"  🎚  Quality    : {f'{height}p max' if height else 'best available'}")
    if mode == "audio":
        label = "MP3" if audio_format == "mp3" else "original stream"
        bitrate_str = f" @ {bitrate} kbps" if audio_format == "mp3" else ""
        print(f"  🎧 Audio      : {label}{bitrate_str}")
    print(f"  📦 Size       : ~{_format_bytes(size) if size else 'unknown'}\n")

    _downloaded_something = False

    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            ydl.download([target_url])
    except Exception as exc:  # noqa: BLE001 - report and let the caller continue
        print(f"\n❌ Download failed:\n   {exc}")
        return False

    if _stdout_is_tty():
        print()

    if not _downloaded_something:
        print("⏭  Nothing new to download — it is already in the archive or on disk.")
        if args.archive:
            print("   Use --no-archive to force a fresh download.")
        print(f"\n📁 Existing files: {output_dir}")
        return True

    print(f"🎉 Done! Files saved in:\n   {output_dir}")
    return True


def _open_downloads_folder(output_dir: Path) -> None:
    """Offer to reveal the destination folder in the file manager."""
    if sys.platform == "win32":
        if not _prompt_yes_no("\n📂 Open downloads folder?", default=True):
            return
        with contextlib.suppress(Exception):
            os.startfile(output_dir)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        if _prompt_yes_no("\n📂 Reveal downloads folder in Finder?", default=False):
            subprocess.run(["open", str(output_dir)], check=False)
    elif shutil.which("xdg-open"):
        if _prompt_yes_no("\n📂 Open downloads folder?", default=False):
            subprocess.run(["xdg-open", str(output_dir)], check=False)


def run(args: argparse.Namespace) -> int:
    """Execute the requested workflow."""
    interactive = _stdin_is_tty()

    if interactive and not args.url:
        _banner()

    if COOKIES_FILE.is_file():
        print(f"  🍪 Cookie file active: {COOKIES_FILE.name}")
    elif args.cookies_from_browser:
        print(f"  🍪 Cookies from browser: {args.cookies_from_browser}")
    else:
        print("  ℹ  No cookies.txt (only needed for age-restricted videos)")

    # A URL supplied on the command line means a single, scriptable run.
    if args.url:
        return 0 if download_once(args, interactive) else 1

    successes = 0
    while True:
        if download_once(args, interactive):
            successes += 1

        if not interactive:
            break
        print("\n" + "─" * 50)
        if not _prompt_yes_no("🔄 Download another video?", default=False):
            break

    if successes:
        _open_downloads_folder(Path(args.output).expanduser() if args.output else DOWNLOAD_DIR)

    if interactive or successes:
        print("\nGoodbye! 👋")
    return 0 if successes else 1


# ── CLI ─────────────────────────────────────────────────────────────────────
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="video-downloader",
        description=f"{APP_NAME} — download video or audio with yt-dlp.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  python main.py                       # interactive wizard\n"
            "  python main.py 'https://youtu.be/ID' # prompts for mode only\n"
            "  python main.py URL -m video -q 1080  # fully non-interactive\n"
            "  python main.py URL -m audio -f mp3 -b 320\n"
            "  python main.py URL -m video -p       # whole playlist\n"
            "  python main.py --cookies-from-browser chrome URL\n"
            "  python main.py --doctor              # check your environment\n"
        ),
    )
    parser.add_argument("url", nargs="?", help="video or playlist URL")
    parser.add_argument(
        "-m",
        "--mode",
        choices=list(MODE_CHOICES),
        help="download mode (default: ask, or 'video' when non-interactive)",
    )
    parser.add_argument(
        "-q",
        "--quality",
        help="max video height, e.g. 1080, 720p, or 'best'",
    )
    parser.add_argument(
        "-b",
        "--bitrate",
        choices=[value for value, _ in AUDIO_BITRATES.values()],
        help="MP3 bitrate in kbps (default: 320)",
    )
    parser.add_argument(
        "-f",
        "--audio-format",
        choices=["mp3", "original"],
        help="audio output: mp3 (converted) or original stream (default: mp3)",
    )
    parser.add_argument(
        "-p",
        "--playlist",
        dest="playlist",
        action="store_true",
        default=None,
        help="download the entire playlist when the URL contains one",
    )
    parser.add_argument(
        "--no-playlist",
        dest="playlist",
        action="store_false",
        help="download only the single video from a playlist URL",
    )
    parser.add_argument(
        "-o", "--output", help=f"destination folder (default: {DEFAULT_DOWNLOAD_DIR})"
    )
    parser.add_argument("--cookies", help="path to a Netscape cookies.txt file")
    parser.add_argument(
        "--cookies-from-browser",
        metavar="BROWSER[:PROFILE]",
        help="read cookies from a browser (chrome, firefox, edge, brave, opera, safari…)",
    )
    parser.add_argument(
        "--no-clipboard", action="store_true", help="do not read the clipboard for a URL"
    )
    parser.add_argument(
        "--no-archive",
        dest="archive",
        action="store_false",
        help="allow downloading items already recorded in the archive",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="show yt-dlp output")
    parser.add_argument("--doctor", action="store_true", help="check the environment and exit")
    parser.add_argument("--version", action="version", version=f"{APP_NAME} {VERSION}")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.doctor:
        return run_doctor()

    if yt_dlp is None:
        print("Error: yt-dlp is not installed.")
        print("Run: pip install -r requirements.txt")
        return 2

    try:
        return run(args)
    except KeyboardInterrupt:
        print("\n\n⏹  Cancelled.")
        return 130
    except EOFError:
        print("\n\n⏹  Input closed.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
