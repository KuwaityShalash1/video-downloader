# 🎬 Video & Audio Downloader

A lightweight, modern command-line video and audio downloader powered by [`yt-dlp`](https://github.com/yt-dlp/yt-dlp).

Supports high-definition merged video downloads, MP3 audio extraction, resolution selection, age-restricted/member-only content handling via cookie authentication, and automatic JavaScript challenge deciphering with Node.js.

---

## ✨ Features

- **Multi-Mode Downloads**:
  - **Video + Audio**: Automatically downloads best video & audio streams and merges them losslessly.
  - **Audio Only (MP3)**: Extracts audio and encodes to MP3 with selectable bitrates (320 kbps, 256 kbps, 192 kbps, 128 kbps).
  - **Video Only**: Downloads raw video stream without audio.
- **Interactive Resolution Picker**: Choose your preferred quality (`1080p`, `720p`, `480p`, etc.) or default to highest available.
- **Age-Restricted & Private Content Support**: Easily loads Netscape-format `cookies.txt` to access restricted videos.
- **Node.js Integration**: Automatically leverages Node.js to solve YouTube's `n-sig` JavaScript deciphering challenges.
- **Windows Double-Click Launcher**: Includes `run.bat` for quick one-click startup on Windows.

---

## 📋 Prerequisites

Before running the downloader, ensure the following are installed on your system:

1. **Python 3.10+**: [python.org](https://www.python.org/downloads/)
2. **FFmpeg** (Required for merging video/audio and MP3 conversion):
   - **Windows** (using winget):
     ```powershell
     winget install Gyan.FFmpeg.Essentials
     ```
   - **macOS** (using Homebrew):
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

Downloaded files will be saved in the `downloads/` folder inside the project directory.

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

> ⚠️ **Warning**: Never commit or share your `cookies.txt` file publicly. It contains active session credentials. This project's `.gitignore` automatically excludes `cookies.txt`.

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
