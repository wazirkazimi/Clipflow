from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from typing import Optional
from pydantic import BaseModel
import yt_dlp
import os
import aiofiles
import time
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base
from datetime import datetime
from itertools import cycle

# --- DATABASE SETUP ---
DATABASE_URL = "sqlite:///./clipflow.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

from youtube_helper import fetch_youtube_video_info
import json

class ProjectDB(Base):
    __tablename__ = "projects"
    id = Column(Integer, primary_key=True, index=True)
    source_type = Column(String, index=True) # youtube_url | file_upload
    source_url = Column(String, nullable=True)
    source_file_path = Column(String, nullable=True)
    heatmap_data = Column(String, nullable=True) # Stored as JSON string
    status = Column(String, default="processing")
    created_at = Column(DateTime, default=datetime.utcnow)

class ClipDB(Base):
    __tablename__ = "clips"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, index=True)
    start_time = Column(Float)
    duration = Column(Float) # 30s | 60s
    output_path = Column(String, nullable=True)
    gameplay_source = Column(String, nullable=True)
    status = Column(String, default="pending")
    exported_at = Column(DateTime, nullable=True)

class BatchDB(Base):
    __tablename__ = "batches"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, index=True)
    num_clips = Column(Integer)
    start_time = Column(Float)
    duration = Column(Float)
    total_completed = Column(Integer, default=0)
    status = Column(String, default="processing")  # processing | ready | failed
    created_at = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)

# --- FastAPI APP ---
app = FastAPI(title="Clipflow API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Since it's a local tool
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve exports as static files
os.makedirs("exports", exist_ok=True)
app.mount("/exports", StaticFiles(directory="exports"), name="exports")

# --- MODELS ---
class YouTubeRequest(BaseModel):
    url: str

class ClipGenerateRequest(BaseModel):
    project_id: int
    start_time: float
    duration: float
    gameplay_source: str = None

class BatchGenerateRequest(BaseModel):
    project_id: int
    num_clips: int
    start_time: float
    duration: float
    rotate_gameplay: bool = True

# --- GAMEPLAY LIBRARY ---
GAMEPLAY_LIBRARY = {
    "subway_surfer": "assets/gameplay/subway_surfer_loop.mp4",
    "mc_parkour": "assets/gameplay/mc_parkour.mp4",
    "temple_run": "assets/gameplay/temple_run.mp4",
    "nfs_car": "assets/gameplay/nfs_car.mp4",
    "minecraft_parkour": "assets/gameplay/minecraft_parkour.mp4",
    "ramp_car": "assets/gameplay/ramp_car.mp4",
    "bgmi": "assets/gameplay/bgmi.mp4",
}

def get_available_gameplay():
    """Returns list of available gameplay videos that exist on disk"""
    available = {}
    for name, path in GAMEPLAY_LIBRARY.items():
        if os.path.exists(path):
            available[name] = path
    return available

# --- MOCK PROCESSING WORKER ---
def process_youtube_video(video_url: str, project_id: int):
    print(f"Began processing youtube URL: {video_url}")
    
    # Actually fetch video info + heatmap, then download
    video_info = fetch_youtube_video_info(video_url, download_video=True)
    
    db = SessionLocal()
    project = db.query(ProjectDB).filter(ProjectDB.id == project_id).first()
    
    if project:
        if video_info:
            project.status = "ready"
            project.source_file_path = video_info.get('filepath')
            if video_info.get('heatmap'):
                project.heatmap_data = json.dumps(video_info['heatmap'])
        else:
            project.status = "failed"
            
        db.commit()
        
    print("Finished processing")
    db.close()

# --- ROUTES ---
@app.get("/")
def read_root():
    return {"message": "Welcome to Clipflow Backend API v2", "version": "2.0.0"}

@app.post("/api/process/youtube")
def process_youtube(req: YouTubeRequest, background_tasks: BackgroundTasks):
    if not req.url or "youtube.com" not in req.url and "youtu.be" not in req.url:
        raise HTTPException(status_code=400, detail="Invalid YouTube URL")
    
    db = SessionLocal()
    # Create project record
    new_project = ProjectDB(source_type="youtube_url", source_url=req.url)
    db.add(new_project)
    db.commit()
    db.refresh(new_project)
    db.close()

    # Dispatch to background
    background_tasks.add_task(process_youtube_video, req.url, new_project.id)
    return {"message": "Processing started", "project_id": new_project.id, "status": "processing"}

@app.post("/api/process/upload")
async def process_upload(file: UploadFile = File(...)):
    # Local file upload handling
    os.makedirs("uploads", exist_ok=True)
    file_path = f"uploads/{file.filename}"
    
    async with aiofiles.open(file_path, 'wb') as out_file:
        content = await file.read()
        await out_file.write(content)
        
    db = SessionLocal()
    new_project = ProjectDB(source_type="file_upload", source_file_path=file_path)
    db.add(new_project)
    db.commit()
    db.refresh(new_project)
    db.close()

    return {"message": "File uploaded successfully", "project_id": new_project.id, "status": "processing", "path": file_path}

@app.get("/api/projects/{project_id}")
def get_project_status(project_id: int):
    db = SessionLocal()
    project = db.query(ProjectDB).filter(ProjectDB.id == project_id).first()
    db.close()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    return {
        "id": project.id,
        "status": project.status,
        "type": project.source_type
    }

from ffmpeg_helper import create_split_screen_short

def generate_clip_worker(clip_id: int, project_id: int, start: float, dur: float, gameplay: str):
    db = SessionLocal()
    clip = db.query(ClipDB).filter(ClipDB.id == clip_id).first()
    project = db.query(ProjectDB).filter(ProjectDB.id == project_id).first()
    
    if not project or not project.source_file_path:
        if clip:
            clip.status = "failed_no_project_source"
            db.commit()
        db.close()
        return

    if clip:
        clip.status = "processing"
        db.commit()
    
    output_path = f"exports/clip_{clip_id}.mp4"
    
    # Verify gameplay file exists
    if not os.path.exists(gameplay):
        if clip:
            clip.status = f"failed: gameplay file not found: {gameplay}"
            db.commit()
        db.close()
        return
    
    success, res_path = create_split_screen_short(
        main_video_path=project.source_file_path,
        gameplay_video_path=gameplay,
        output_path=output_path,
        start_time=start,
        duration=dur
    )
    
    if clip:
        if success:
            clip.status = "ready"
            clip.output_path = output_path
        else:
            clip.status = f"failed: {res_path}"
        
        db.commit()
    db.close()

def generate_batch_worker(batch_id: int, project_id: int, num_clips: int, start_time: float, duration: float, rotate_gameplay: bool):
    """
    Generates multiple clips with optional gameplay rotation.
    """
    db = SessionLocal()
    batch = db.query(BatchDB).filter(BatchDB.id == batch_id).first()
    project = db.query(ProjectDB).filter(ProjectDB.id == project_id).first()
    
    if not batch or not project or not project.source_file_path:
        if batch:
            batch.status = "failed_no_source"
            db.commit()
        db.close()
        return
    
    batch.status = "processing"
    db.commit()
    
    # Get available gameplay videos
    available_gameplay = get_available_gameplay()
    if not available_gameplay:
        batch.status = "failed_no_gameplay"
        db.commit()
        db.close()
        return
    
    gameplay_list = list(available_gameplay.values())
    
    if rotate_gameplay and len(gameplay_list) > 1:
        # Rotate through different gameplay videos
        gameplay_cycle = cycle(gameplay_list)
    else:
        # Use the first available gameplay video for all clips
        gameplay_cycle = cycle([gameplay_list[0]])
    
    try:
        for clip_index in range(num_clips):
            # Get next gameplay video in rotation
            selected_gameplay = next(gameplay_cycle)
            
            # Create clip
            clip = ClipDB(
                project_id=project_id,
                start_time=start_time,
                duration=duration,
                gameplay_source=selected_gameplay
            )
            db.add(clip)
            db.commit()
            db.refresh(clip)
            
            output_path = f"exports/batch_{batch_id}_clip_{clip_index}.mp4"
            
            success, result = create_split_screen_short(
                main_video_path=project.source_file_path,
                gameplay_video_path=selected_gameplay,
                output_path=output_path,
                start_time=start_time,
                duration=duration
            )
            
            if success:
                clip.status = "ready"
                clip.output_path = output_path
                batch.total_completed += 1
            else:
                clip.status = f"failed: {result}"
            
            db.commit()
        
        batch.status = "ready"
        db.commit()
        print(f"Batch {batch_id} completed: {batch.total_completed}/{num_clips} clips")
        
    except Exception as e:
        print(f"Error in batch generation: {e}")
        batch.status = f"failed: {str(e)}"
        db.commit()
    finally:
        db.close()

@app.post("/api/clips/generate")
def request_clip_generation(req: ClipGenerateRequest, background_tasks: BackgroundTasks):
    db = SessionLocal()
    project = db.query(ProjectDB).filter(ProjectDB.id == req.project_id).first()
    
    if not project:
        db.close()
        raise HTTPException(status_code=404, detail="Project not found")
    
    # If no gameplay source specified, pick first available
    gameplay_source = req.gameplay_source
    if not gameplay_source:
        available = get_available_gameplay()
        if not available:
            db.close()
            raise HTTPException(status_code=400, detail="No gameplay videos available")
        gameplay_source = list(available.values())[0]
    
    # Verify gameplay file exists
    if not os.path.exists(gameplay_source):
        db.close()
        raise HTTPException(status_code=400, detail=f"Gameplay video not found: {gameplay_source}")
    
    new_clip = ClipDB(
        project_id=req.project_id,
        start_time=req.start_time,
        duration=req.duration,
        gameplay_source=gameplay_source,
    )
    db.add(new_clip)
    db.commit()
    db.refresh(new_clip)
    db.close()
    
    background_tasks.add_task(generate_clip_worker, new_clip.id, req.project_id, req.start_time, req.duration, gameplay_source)
    return {"message": "Clip queued for composition", "clip_id": new_clip.id, "status": "pending", "gameplay": gameplay_source}

@app.get("/api/clips/{clip_id}")
def get_clip_status(clip_id: int):
    db = SessionLocal()
    clip = db.query(ClipDB).filter(ClipDB.id == clip_id).first()
    db.close()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")
    return {"id": clip.id, "status": clip.status, "output_path": clip.output_path}

@app.post("/api/clips/batch")
def request_batch_generation(req: BatchGenerateRequest, background_tasks: BackgroundTasks):
    """
    Generates multiple clips with optional gameplay rotation.
    If rotate_gameplay=True and multiple gameplay videos exist, each clip uses a different one.
    """
    db = SessionLocal()
    project = db.query(ProjectDB).filter(ProjectDB.id == req.project_id).first()
    
    if not project:
        db.close()
        raise HTTPException(status_code=404, detail="Project not found")
    
    if project.status != "ready":
        db.close()
        raise HTTPException(status_code=400, detail=f"Project not ready. Current status: {project.status}")
    
    available = get_available_gameplay()
    if not available:
        db.close()
        raise HTTPException(status_code=400, detail="No gameplay videos available")
    
    new_batch = BatchDB(
        project_id=req.project_id,
        num_clips=req.num_clips,
        start_time=req.start_time,
        duration=req.duration
    )
    db.add(new_batch)
    db.commit()
    db.refresh(new_batch)
    db.close()
    
    background_tasks.add_task(
        generate_batch_worker,
        new_batch.id,
        req.project_id,
        req.num_clips,
        req.start_time,
        req.duration,
        req.rotate_gameplay
    )
    
    return {
        "message": "Batch generation queued",
        "batch_id": new_batch.id,
        "num_clips": req.num_clips,
        "rotate_gameplay": req.rotate_gameplay,
        "available_gameplay": len(available),
        "status": "pending"
    }

@app.get("/api/batches/{batch_id}")
def get_batch_status(batch_id: int):
    """
    Gets the status of a batch generation task.
    """
    db = SessionLocal()
    batch = db.query(BatchDB).filter(BatchDB.id == batch_id).first()
    db.close()
    
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    return {
        "id": batch.id,
        "project_id": batch.project_id,
        "num_clips": batch.num_clips,
        "total_completed": batch.total_completed,
        "status": batch.status,
        "progress": f"{batch.total_completed}/{batch.num_clips}"
    }

@app.get("/api/gameplay/available")
def list_available_gameplay():
    """
    Lists all available gameplay videos.
    """
    available = get_available_gameplay()
    return {
        "total": len(available),
        "gameplay_videos": available
    }

@app.get("/api/health")
def health_check():
    """
    Health check endpoint.
    """
    available_gameplay = get_available_gameplay()
    return {
        "status": "healthy",
        "service": "Clipflow API v2",
        "available_gameplay_count": len(available_gameplay)
    }
