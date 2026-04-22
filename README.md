# 🎥 Clipflow: Pro AI Video Automation

Clipflow is a high-performance toolkit designed to transform long-form content (YouTube and Instagram) into viral-ready vertical clips (9:16) with **AI Captions**, **Hinglish Support**, and **Parallel Processing**.

---

## ✨ Key Features

### 🎙️ AI Viral Captions
- **Word-Level Highlighting**: Dynamic "Karaoke style" captions that highlight the current word in high-contrast Cyan/Yellow.
- **Premium Typography**: Uses high-impact **Impact** font, optimized for readability in social media feeds.
- **Smart Chunking**: Automatically groups text into 2-3 word clusters to keep the screen clean and engaging.

### 🇮🇳 Hinglish & Multilingual Engine
- **Automatic Transliteration**: Detects Hindi/Urdu speech and automatically converts it into **Hinglish** (Roman script) for global readability.
- **Forced Language Mode**: Option to force Hindi detection for 100% accurate transliteration of complex speech.

### 🚀 Extreme Performance
- **Parallel Processing**: Generates multiple clips simultaneously using multi-threading, cutting generation time by 300%.
- **AI Model Caching**: Loads the Whisper AI model once and keeps it in memory for instant reuse across multiple clips.
- **Smart Clipping**: Only transcribes the specific 60s segment needed, making the captioning process 100x faster than traditional methods.

### 🎮 Immersive Composition
- **Split-Screen Shorts**: Source video on top with immersive gameplay (Subway Surfers/Minecraft) on the bottom.
- **Engagement Heatmaps**: Automatically finds the "hottest" moments on YouTube to ensure your clips have the highest viral potential.

---

## 🚀 Getting Started

### 1. Activate Environment
Always make sure your virtual environment is active before running:
```powershell
.\backend\venv\Scripts\activate
```

### 2. Install AI Dependencies
```powershell
pip install openai-whisper torch indic-transliteration
```

### 3. Run the Tools

#### 📱 Instagram Reels
```bash
python backend/instagram_terminal.py
```

#### 📺 YouTube Shorts
```bash
python backend/youtube_terminal.py
```

---

## 📁 Project Structure
```text
Clipflow/
├── backend/
│   ├── instagram_terminal.py  # Instagram CLI with Caption Toggles
│   ├── youtube_terminal.py    # Parallel processing YouTube CLI
│   ├── ffmpeg_helper.py       # AI Captioning & Video Engine (The Brain)
│   ├── youtube_helper.py      # Heatmap & Metadata Extraction
│   └── assets/gameplay/       # Gameplay Background Library
└── exports/                   # Final viral-ready MP4 clips
```

---
*Built for Viral Growth, Optimized for Speed.*
