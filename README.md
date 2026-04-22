# 🎥 Clipflow: AI-Powered Short-Form Content Generator

Clipflow is a high-performance terminal-based toolkit designed to transform long-form content (YouTube and Instagram) into viral-ready vertical clips (9:16) with gameplay overlays.

## ✨ Features

-   **Instagram Terminal Tool**: Download any Instagram Reel and instantly convert it into a split-screen short with a gameplay background.
-   **YouTube Viral Generator**: Automatically finds the most engaging moments in a YouTube video using **Engagement Heatmap Data** and crops them into viral-ready clips.
-   **Split-Screen Composition**: Professional 1080x1920 (9:16) output with the source video on top and immersive gameplay (Subway Surfers/Minecraft) on the bottom.
-   **Automatic Asset Recovery**: Detects missing or corrupted gameplay assets and downloads high-quality loops automatically.

---

## 🚀 Getting Started

# Make sure your venv is active eveytime 
```
.\backend\venv\Scripts\activate
```

### 1. Prerequisites
-   **Python 3.8+**
-   **FFmpeg** (Handled automatically by the script via `static-ffmpeg`)
-   **yt-dlp** (For high-speed video extraction)

### 2. Usage

#### 📱 For Instagram Reels
Convert an Instagram Reel into a 9:16 split-screen clip:
```bash
cd backend
python instagram_terminal.py
```
-   **Input**: Paste your Reel URL.
-   **Output**: Saved in `backend/exports/instagram/`.

#### 📺 For YouTube Videos
Generate multiple viral clips from a single YouTube URL:
```bash
cd backend
python youtube_terminal.py
```
-   **Input**: Paste YouTube URL & number of clips desired.
-   **Feature**: The script automatically picks the "hottest" moments based on viewer engagement!
-   **Output**: Saved in `backend/exports/youtube/`.

---

## 📁 Project Structure

```text
Clipflow/
├── backend/
│   ├── instagram_terminal.py  # Main CLI for Instagram
│   ├── youtube_terminal.py    # Main CLI for YouTube
│   ├── ffmpeg_helper.py       # Core video processing engine
│   ├── instagram_helper.py    # Instagram extraction logic
│   ├── youtube_helper.py      # YouTube info & heatmap logic
│   └── assets/gameplay/       # Background video library
└── exports/                   # Final rendered clips
```

## 🛠 Troubleshooting
-   **Red/Black Screen**: Usually means the source video was interrupted. The script now automatically detects dummy files and tries to re-download them.
-   **FFmpeg errors**: Ensure you have a stable internet connection for the first run, as it may need to download the FFmpeg binaries.

---
*Built for speed, simplicity, and viral potential.*
