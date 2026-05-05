# Clipflow 🎬

Clipflow is an automated, AI-powered video clipping pipeline designed to turn long-form YouTube and Instagram videos into viral-ready, highly engaging Shorts, Reels, and TikToks. 

It completely automates the extraction, transcription, captioning, and rendering processes.

## 🚀 Key Features

### 1. Hybrid AI Subtitles (Perfect Hinglish)
- **Word-by-Word Animation**: Dynamically highlights the currently spoken word in bright yellow.
- **Fast Pacing**: Snappy 2-3 word subtitle chunks to match fast-paced scrolling behavior.
- **Center-Split Alignment**: Captions perfectly positioned on the split-screen boundary (`\an5`), ideal for vertical content.
- **Smart Hinglish Transliteration**: Natively processes Hindi audio and transcribes it into perfect **Roman Hindi**. The pipeline intercepts Devanagari script, applies Schwa deletion (e.g. converting "तमा" to "tum"), and forces English keywords into **ALL CAPS** for maximum emphasis!

### 2. AI NLP Engine (Hook → Value → Payoff)
- **Beyond Mathematical Trimming**: If a YouTube video lacks a Most-Replayed heatmap, the engine no longer falls back to random guessing.
- **Structural Transcript Analysis**: The pipeline downloads the JSON3 auto-captions from YouTube directly and scans them for structural hooks ("secret", "mistake", "listen"), value propositions, and payoffs ("growth", "views").
- **Speech Density Scoring**: Analyzes Words-Per-Second to identify high-energy, fast-paced moments that make viewers stop scrolling.
- **Heatmap Synergy**: When a YouTube heatmap *is* available, the NLP Engine uses the retention peaks to find the exact sentence where the speaker drops the Hook, adjusting the clip's start time for maximum impact.

### 3. Modular Output Layouts
- **Vertical Split-Screen**: Places the speaker up top and a high-retention gameplay video (like Minecraft Parkour or GTA V) on the bottom. Automatically rotates through gameplay backgrounds for batch processing.
- **Full Widescreen (16:9)**: Toggleable option for producing standard YouTube clips without the split-screen.

### 4. High-Performance Batch Processing
- **Parallel FFmpeg Rendering**: Processes multiple vertical clips simultaneously.
- **Thread-Safe AI Transcription**: Whisper AI runs synchronously to prevent memory overflows while FFmpeg handles the heavy video encoding concurrently.
- **No-Download Streaming**: Uses `yt-dlp` to stream specific time chunks of the source video directly into FFmpeg, drastically reducing local storage requirements and increasing speed by 100x compared to downloading full 2-hour podcasts.

## 🛠️ Usage

To generate YouTube clips:
```bash
cd backend
# Make sure your virtual environment is active!
python youtube_terminal.py
```
1. Paste the URL.
2. Choose your clip duration and batch size.
3. Choose vertical or horizontal orientation.
4. The AI handles the rest, outputting your viral clips to `backend/exports/youtube/`.

*(Note: Advanced Face Tracking and Dead-Space Trimming modules were deprecated to prioritize extreme speed and cross-platform terminal stability without Unicode errors.)*
