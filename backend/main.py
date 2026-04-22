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

Base.metadata.create_all(bind=engine)

# --- FastAPI APP ---
app = FastAPI(title="Clipflow API", version="1.0.0")

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
    gameplay_source: str = "library/mc_parkour.mp4"

# --- LOCAL DUMMY LIBRARY ---
# In reality, this checks the local gameplay library dir.
GAMEPLAY_LIBRARY = ["mc_parkour.mp4", "subway_surfer_loop.mp4"]

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
    return {"message": "Welcome to Clipflow Backend API"}

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
        clip.status = "failed_no_project_source"
        db.commit()
        db.close()
        return

    clip.status = "processing"
    db.commit()
    
    output_path = f"exports/clip_{clip_id}.mp4"
    
    # We pass the default gameplay video if it exists, else we need a dummy or the command will fail.
    # In Phase 2, we assume gameplay file exists in 'assets/gameplay' path.
    success, res_path = create_split_screen_short(
        main_video_path=project.source_file_path,
        gameplay_video_path=gameplay,
        output_path=output_path,
        start_time=start,
        duration=dur
    )
    
    if success:
        clip.status = "ready"
        clip.output_path = output_path
    else:
        clip.status = f"failed: {res_path}"
        
    db.commit()
    db.close()

@app.post("/api/clips/generate")
def request_clip_generation(req: ClipGenerateRequest, background_tasks: BackgroundTasks):
    db = SessionLocal()
    new_clip = ClipDB(
        project_id=req.project_id,
        start_time=req.start_time,
        duration=req.duration,
        gameplay_source=req.gameplay_source,
    )
    db.add(new_clip)
    db.commit()
    db.refresh(new_clip)
    db.close()
    
    background_tasks.add_task(generate_clip_worker, new_clip.id, req.project_id, req.start_time, req.duration, req.gameplay_source)
    return {"message": "Clip queued for composition", "clip_id": new_clip.id, "status": "pending"}

@app.get("/api/clips/{clip_id}")
def get_clip_status(clip_id: int):
    db = SessionLocal()
    clip = db.query(ClipDB).filter(ClipDB.id == clip_id).first()
    db.close()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")
    return {"id": clip.id, "status": clip.status, "output_path": clip.output_path}
