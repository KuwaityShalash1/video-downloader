# 🎬 Video & Audio Downloader

A lightweight, modern CLI video and audio downloader powered by [`yt-dlp`](https://github.com/yt-dlp/yt-dlp).

It merges high-definition video with the best audio into a universally compatible **MP4**, extracts **MP3** files with embedded album art and metadata, and can also grab the raw video stream. Use it interactively or drive it entirely from the command line.

---

## ✨ Features

- **Three download modes**
  - **Video + Audio** — best video and best audio streams merged losslessly into **MP4**.
  - **Audio only** — MP3 (up to 320 kbps) with the thumbnail as album art, or keep the original stream with no re-encode.
  - **Video only** — the raw video stream without audio.
- **Command-line flags for everything** — every prompt has a flag, so the tool can run unattended in scripts.
- **📋 Automatic clipboard detection** — copy a URL in your browser and just press `Enter`.
- **📑 Playlist intelligence** — a link that contains a playlist asks whether you want the single video or the whole playlist; playlists are saved into their own folder with numbered filenames.
- **🎯 Resolution picker** — `1080p`, `720p`, `480p`… or best available.
- **⏯ Resumable and retried downloads** — partial files continue where they stopped, transient network errors are retried, and finished media is remembered in an archive so it is never downloaded twice (`--no-archive` to override).
- **🔒 Age-restricted & private content** — reuse your browser session with `--cookies-from-browser`, or load a Netscape `cookies.txt`.
- **⚡ Node.js integration** — solves YouTube's `n-sig` JavaScript deciphering challenges automatically.
- **🩺 Built-in doctor** — `--doctor` checks Python, yt-dlp, FFmpeg, Node.js, cookies, and write permissions.
- **🚀 One-click launchers** — `run.bat` on Windows, `run.sh` on macOS/Linux.

---

## 📋 Prerequisites

1. **Python 3.10+** — [python.org](https://www.python.org/downloads/)
2. **FFmpeg** — required for merging and MP3 conversion:
   - **Windows:** `winget install Gyan.FFmpeg.Essentials`
   - **macOS:** `brew install ffmpeg`
   - **Linux:** `sudo apt update && sudo apt install ffmpeg`
3. **Node.js** (recommended) — helps yt-dlp solve YouTube signature challenges:
   - [nodejs.org](https://nodejs.org/) or `winget install OpenJS.NodeJS`

Run `python main.py --doctor` at any time to verify the setup.

---

## 🚀 Quick Start

### 1. Clone the repository
```bash
git clone https://github.com/KuwaityShalash1/video-downloader.git
cd video-downloader
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Run the application
- **Windows:** double-click `run.bat` (or `python main.py`)
- **macOS / Linux:** `./run.sh` (or `python3 main.py`)

Downloaded files go to `downloads/`.

---

## 🕹 Usage

### Interactive wizard
```bash
python main.py
```
The wizard offers the clipboard URL, asks for the mode, shows the title/channel/duration, lets you pick a resolution, and then downloads.

### Non-interactive (scripts, cron, batch files)
```bash
# Video with a 1080p cap
python main.py "https://youtu.be/VIDEO_ID" -m video -q 1080

# MP3 at 256 kbps
python main.py "https://youtu.be/VIDEO_ID" -m audio -b 256

# Audio without re-encoding (keeps m4a/opus)
python main.py "https://youtu.be/VIDEO_ID" -m audio -f original

# Video stream only, 720p, into a custom folder
python main.py "https://youtu.be/VIDEO_ID" -m video-only -q 720 -o ~/Videos

# Whole playlist, best quality
python main.py "https://www.youtube.com/playlist?list=PL123" -p
```

### Options

| Flag | Description |
| --- | --- |
| `url` | Video or playlist URL (omit it to use the wizard) |
| `-m, --mode` | `video`, `audio`, or `video-only` (default: ask, or `video` when non-interactive) |
| `-q, --quality` | Maximum height, e.g. `1080`, `720p`, or `best` |
| `-b, --bitrate` | MP3 bitrate: `320` (default), `256`, `192`, `128` |
| `-f, --audio-format` | `mp3` (converted) or `original` (no re-encode) |
| `-p, --playlist` | Download the entire playlist from a playlist URL |
| `--no-playlist` | Download only the single video from a playlist URL |
| `-o, --output` | Destination folder (default: `./downloads`) |
| `--cookies FILE` | Path to a Netscape `cookies.txt` |
| `--cookies-from-browser` | Read cookies from a browser, e.g. `chrome` or `firefox:default-release` |
| `--no-clipboard` | Do not read the clipboard |
| `--no-archive` | Re-download items already recorded in the archive |
| `-v, --verbose` | Show raw yt-dlp output |
| `--doctor` | Check the environment and exit |
| `--version` | Print the version |

### Environment variables

| Variable | Purpose |
| --- | --- |
| `VD_OUTPUT_DIR` | Default destination folder |
| `VD_COOKIES` | Default `cookies.txt` path |

---

## 🍪 Age-Restricted & Private Content

**Recommended:** reuse the session from a browser you are already signed in to:

```bash
python main.py --cookies-from-browser chrome "https://youtu.be/VIDEO_ID"
```

Supported names: `brave`, `chrome`, `chromium`, `edge`, `firefox`, `opera`, `safari`, `vivaldi`, `whale`, optionally with a profile: `firefox:default-release`.

<details>
<summary>Alternative: export a cookies file</summary>

1. Install the browser extension [Get cookies.txt LOCALLY](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc).
2. Sign in to [youtube.com](https://www.youtube.com).
3. Open the extension, click **Export**, and save the file as `cookies.txt` in this project's root folder.
4. Run the program as usual — it is detected automatically, or pass it explicitly with `--cookies path/to/cookies.txt`.

</details>

> ⚠️ **Warning:** never commit or share your cookies. This project's `.gitignore` already excludes `cookies.txt`.

---

## 📂 Output

```
downloads/
├── Some video title.mp4
├── Another video.mp4
└── My Playlist/
    ├── 001 - First track.mp3
    └── 002 - Second track.mp3
```

Finished downloads are recorded in `.download-archive.txt` so repeat runs skip them. Delete that file (or pass `--no-archive`) to download everything again.

---

## 🩺 Troubleshooting

| Symptom | Fix |
| --- | --- |
| `FFmpeg is required` | Install FFmpeg (see Prerequisites) and reopen the terminal. |
| `HTTP Error 403` while downloading media | The site is refusing the request: try `--cookies-from-browser chrome`, or update yt-dlp (`pip install -U yt-dlp`). |
| `Sign in to confirm your age` | The video is age-restricted — use `--cookies-from-browser` with a signed-in browser. |
| `Requested format is not available` | Lower the quality, e.g. `-q 720`. |
| Nothing happens / instantly skipped | The item is in `.download-archive.txt`; use `--no-archive`. |
| A site stops working | Run `pip install -U yt-dlp`; extractors are fixed constantly. |

---

## 🛠 Development

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt

ruff check .          # lint
pytest                # unit tests, no network required
```

The test suite covers URL/playlist parsing, quality parsing, format selection, size estimation, option assembly, and the CLI surface. CI runs lint and tests on Python 3.10 and 3.12 for every push and pull request.

### Project structure

```
video-downloader/
├── .github/workflows/ci.yml   # Lint + tests on every push
├── downloads/                 # Default destination (git-ignored)
├── tests/test_main.py         # Unit tests
├── .gitignore
├── LICENSE                    # MIT
├── main.py                    # CLI application
├── pyproject.toml             # ruff / pytest configuration
├── requirements.txt           # Runtime dependencies
├── requirements-dev.txt       # Test and lint dependencies
├── run.bat                    # Windows launcher
├── run.sh                     # macOS / Linux launcher
└── README.md
```

---

## 📄 License

Distributed under the [MIT License](LICENSE).
