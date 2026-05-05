# Clipflow v2.0 - Quick Start Guide

## ✅ What's Completed
YouTube and Instagram batch generation with **smart gameplay rotation** is now fully implemented and ready to use!

## 🚀 Quick Start (3 Steps)

### Step 1: Download Gameplay Videos
```bash
cd backend
python setup_gameplay_videos.py
```
This downloads 5 new gameplay videos and extracts middle sections. You'll have 7 total videos available.

### Step 2: Start the APIs
In Terminal 1:
```bash
python -m uvicorn main:app --port 8000
```

In Terminal 2:
```bash
python -m uvicorn instagram_main:app --port 8001
```

### Step 3: Generate Batches
**For YouTube:**
```bash
python example_youtube_batch.py
```

**For Instagram:**
```bash
python example_batch_generation.py
```

## 📝 What You Get

### YouTube API (Port 8000)
- **New Endpoint:** `POST /api/clips/batch` - Generate multiple clips with rotating gameplay
- **New Endpoint:** `GET /api/batches/{id}` - Check progress
- **New Endpoint:** `GET /api/gameplay/available` - List available gameplay videos
- **New Endpoint:** `GET /api/health` - Health check

### Instagram API (Port 8001)  
- **New Endpoint:** `POST /api/composites/batch` - Generate multiple composites with rotating gameplay
- **New Endpoint:** `GET /api/composite-batches/{id}` - Check progress
- **New Endpoint:** `GET /api/gameplay/available` - List available gameplay videos
- **New Endpoint:** `GET /api/health` - Health check

## 🎬 Gameplay Rotation Example

Request batch generation with 7 clips:
```bash
curl -X POST http://localhost:8000/api/clips/batch \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": 1,
    "num_clips": 7,
    "start_time": 0,
    "duration": 30,
    "rotate_gameplay": true
  }'
```

Result: Each clip uses a **different gameplay video**
- clip_0 → subway_surfer
- clip_1 → mc_parkour  
- clip_2 → temple_run
- clip_3 → nfs_car
- clip_4 → minecraft_parkour
- clip_5 → ramp_car
- clip_6 → bgmi

## 📊 Available Gameplay Videos (7 Total)

1. **subway_surfer** - Subway Surfers gameplay
2. **mc_parkour** - Minecraft parkour
3. **temple_run** - Temple Run (5-15min section)
4. **nfs_car** - Need for Speed
5. **minecraft_parkour** - Minecraft parkour
6. **ramp_car** - Ramp car
7. **bgmi** - BGMI mobile game

*Videos 1-2 are included. Videos 3-7 are downloaded by setup_gameplay_videos.py*

## 📂 Output Files

All generated clips saved to: `exports/`

Format: `batch_{batch_id}_clip_{index}.mp4`

Example: 
- `batch_1_clip_0.mp4`
- `batch_1_clip_1.mp4`
- ... up to `batch_1_clip_6.mp4`

## 📖 Documentation

- **YOUTUBE_API_v2_REFERENCE.txt** - Complete YouTube API docs
- **YOUTUBE_BATCH_RELEASE_NOTES.txt** - Release notes and features
- **COMPLETION_STATUS_v2.0.txt** - Full status report
- **example_youtube_batch.py** - YouTube working example
- **example_batch_generation.py** - Instagram working example

## ⚡ Performance

- 7 clips (30 sec each): ~5-7 minutes
- 15 clips (30 sec each): ~10-15 minutes  
- 30 clips (30 sec each): ~20-30 minutes

*Depends on CPU speed and disk speed*

## 🧪 Test It

```bash
# Check YouTube API
curl http://localhost:8000/api/health

# Check Instagram API
curl http://localhost:8001/api/health

# List available gameplay
curl http://localhost:8000/api/gameplay/available
```

## 💡 Key Features

✅ **Batch Generation** - Create multiple clips in one API call
✅ **Smart Rotation** - Each clip automatically gets different gameplay
✅ **Progress Tracking** - Monitor batch progress in real-time
✅ **Both Platforms** - Works on YouTube and Instagram simultaneously
✅ **Auto Scaling** - Works with any number of clips (7, 15, 30, 100+)

## 🎯 Use Cases

1. **YouTube Shorts Creator** - Generate 15 shorts from 1 video with different gameplay
2. **Content Batching** - Create variety without manual gameplay selection
3. **Automation** - Set and forget - system rotates gameplay automatically
4. **Consistency** - All clips same format, duration, and quality

## 📞 Need Help?

1. Check if gameplay videos exist: `assets/gameplay/` should have 7 .mp4 files
2. Run setup script again: `python setup_gameplay_videos.py`
3. Check API is running: `curl http://localhost:8000/api/health`
4. Read full docs: See documentation files listed above

## 🎉 You're Ready!

Everything is set up and ready to use. Start with Step 1 above to download the remaining gameplay videos, then you can generate batches!
