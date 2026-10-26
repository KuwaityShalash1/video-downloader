# 🎬 Video & Audio Downloader

A lightweight, modern CLI video and audio downloader powered by [`yt-dlp`](https://github.com/yt-dlp/yt-dlp).

Supports high-definition merged MP4 video downloads, MP3 audio extraction with embedded album art and metadata, resolution picking, playlist detection, age-restricted/member-only content via cookie authentication, and automatic JavaScript deciphering with Node.js.

---

## ✨ Features

- **Multi-Mode Downloads**:
  - **Video + Audio**: Automatically downloads the best video & audio streams and losslessly merges them into a universally compatible **MP4**.
  - **Audio Only (MP3)**: Extracts audio, converts to MP3 (up to 320 kbps), and embeds the **video thumbnail as album art** along with artist and title metadata tags.
  - **Video Only**: Downloads raw video stream without audio.
- **📋 Automatic Clipboard Detection**: Copies a URL in your browser and it is automatically suggested when you open the program — just hit `Enter`!
- **📑 Playlist Intelligence**: If you paste a link containing a playlist, the tool asks whether you want to download just the single video or the entire playlist.
- **🎯 Resolution Picker**: Choose `1080p`, `720p`, `480p`, etc., or default to highest available.
- **🔄 Batch / Continuous Mode**: Download multiple videos in a row without having to restart the script.
- **📂 Open Downloads Folder**: Offers to open the destination folder in Windows Explorer right after downloading.
- **🔒 Age-Restricted & Private Content**: Seamlessly loads Netscape-format `cookies.txt` for restricted or member-only videos.
- **⚡ Node.js Integration**: Automatically leverages Node.js to solve YouTube's `n-sig` JavaScript deciphering challenges.
- **🚀 One-Click Launcher**: Double-click `run.bat` on Windows to start immediately.

---

## 📋 Prerequisites

1. **Python 3.10+**: [python.org](https://www.python.org/downloads/)
2. **FFmpeg** (Required for merging video/audio and MP3 conversion):
   - **Windows** (via winget):
     ```powershell
     winget install Gyan.FFmpeg.Essentials
     ```
   - **macOS** (via Homebrew):
     ```bash
     brew install ffmpeg
     ```
   - **Linux** (Debian/Ubuntu):
     ```bash
     sudo apt update && sudo apt install ffmpeg
     ```
3. **Node.js** (Recommended for YouTube signature deciphering):
   - Download from [nodejs.org](https://nodejs.org/) or install via winget:
     ```powershell
     winget install OpenJS.NodeJS
     ```

---

## 🚀 Quick Start

### 1. Clone the repository
```bash
git clone https://github.com/YOUR_USERNAME/video-downloader.git
cd video-downloader
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Run the application
- On **Windows**: Double-click `run.bat` or run:
  ```bash
  python main.py
  ```
- On **macOS / Linux**:
  ```bash
  python3 main.py
  ```

Downloaded files are saved in the `downloads/` directory inside the project.

---

## 🍪 Age-Restricted & Private Content Setup

If a video requires YouTube login verification or is age-restricted:

1. Install the browser extension [Get cookies.txt LOCALLY](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc).
2. Go to [youtube.com](https://www.youtube.com) and make sure you are signed in.
3. Open the extension, click **Export**, and save the file as `cookies.txt` inside this project's root folder:
   ```
   video-downloader/
   ├── cookies.txt   <-- Place here
   ├── main.py
   └── ...
   ```
4. Run the program as usual. The downloader will detect the cookies file automatically.

> ⚠️ **Warning**: Never commit or share your `cookies.txt` file publicly. This project's `.gitignore` automatically excludes `cookies.txt`.

---

## 📂 Project Structure

```
video-downloader/
├── downloads/            # Destination directory for all downloaded media
├── .gitignore            # Excludes downloads, virtualenvs, and sensitive cookies
├── LICENSE               # MIT License
├── main.py               # Main CLI application
├── README.md             # Project documentation
├── requirements.txt      # Python dependencies
└── run.bat               # Windows quick-launch script
```

---

## 📄 License

Distributed under the [MIT License](LICENSE).
