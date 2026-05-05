from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import os
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base
from datetime import datetime
import json
from itertools import cycle

# --- DATABASE SETUP ---
DATABASE_URL = "sqlite:///./clipflow_instagram.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

from instagram_helper import fetch_instagram_reel
from ffmpeg_helper import create_reel_composite_video

class InstagramProjectDB(Base):
    __tablename__ = "instagram_projects"
    id = Column(Integer, primary_key=True, index=True)
    reel_url = Column(String, index=True)
    video_file_path = Column(String, nullable=True)
    duration = Column(Float, nullable=True)  # Duration in seconds
    status = Column(String, default="processing")
    created_at = Column(DateTime, default=datetime.utcnow)

class InstagramCompositeDB(Base):
    __tablename__ = "instagram_composites"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, index=True)
    gameplay_source = Column(String, nullable=True)
    output_video_path = Column(String, nullable=True)
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)

class InstagramBatchDB(Base):
    __tablename__ = "instagram_batches"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, index=True)
    num_clips = Column(Integer)
    total_completed = Column(Integer, default=0)
    status = Column(String, default="processing")  # processing | ready | failed
    created_at = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)

# --- FastAPI APP ---
app = FastAPI(title="Clipflow Instagram API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve exports as static files
os.makedirs("exports", exist_ok=True)
app.mount("/exports", StaticFiles(directory="exports"), name="exports")

# --- AVAILABLE GAMEPLAY VIDEOS ---
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

# --- MODELS ---
class InstagramReelRequest(BaseModel):
    url: str

class CompositeVideoRequest(BaseModel):
    project_id: int
    gameplay_source: str = None  # If None, will pick from available

class BatchCompositeRequest(BaseModel):
    project_id: int
    num_clips: int = 5
    rotate_gameplay: bool = True  # Rotate through different gameplay videos

# --- PROCESSING WORKERS ---
def process_instagram_reel(reel_url: str, project_id: int):
    print(f"Started processing Instagram reel: {reel_url}")
    
    try:
        # Download the reel
        reel_info = fetch_instagram_reel(reel_url, download_video=True)
        
        db = SessionLocal()
        project = db.query(InstagramProjectDB).filter(InstagramProjectDB.id == project_id).first()
        
        if project:
            if reel_info and reel_info.get('filepath'):
                project.status = "ready"
                project.video_file_path = reel_info.get('filepath')
                project.duration = reel_info.get('duration')
                db.commit()
            else:
                project.status = "failed"
                db.commit()
        
        db.close()
        print("Finished processing Instagram reel")
        
    except Exception as e:
        print(f"Error processing reel: {e}")
        db = SessionLocal()
        project = db.query(InstagramProjectDB).filter(InstagramProjectDB.id == project_id).first()
        if project:
            project.status = f"failed: {str(e)}"
            db.commit()
        db.close()

def generate_composite_worker(composite_id: int, project_id: int, gameplay: str):
    db = SessionLocal()
    composite = db.query(InstagramCompositeDB).filter(InstagramCompositeDB.id == composite_id).first()
    project = db.query(InstagramProjectDB).filter(InstagramProjectDB.id == project_id).first()
    
    if not project or not project.video_file_path:
        if composite:
            composite.status = "failed_no_project_video"
            db.commit()
        db.close()
        return

    if composite:
        composite.status = "processing"
        db.commit()
    
    output_path = f"exports/instagram_composite_{composite_id}.mp4"
    
    success, result = create_reel_composite_video(
        reel_video_path=project.video_file_path,
        gameplay_video_path=gameplay,
        output_path=output_path
    )
    
    if composite:
        if success:
            composite.status = "ready"
            composite.output_video_path = output_path
        else:
            composite.status = f"failed: {result}"
        
        db.commit()
    db.close()

def generate_batch_composites(batch_id: int, project_id: int, num_clips: int, rotate_gameplay: bool):
    """
    Generates multiple composite videos with optional gameplay rotation.
    If rotate_gameplay=True, distributes different gameplay videos across clips.
    """
    db = SessionLocal()
    batch = db.query(InstagramBatchDB).filter(InstagramBatchDB.id == batch_id).first()
    project = db.query(InstagramProjectDB).filter(InstagramProjectDB.id == project_id).first()
    
    if not batch or not project or not project.video_file_path:
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
            
            # Create composite
            composite = InstagramCompositeDB(
                project_id=project_id,
                gameplay_source=selected_gameplay
            )
            db.add(composite)
            db.commit()
            db.refresh(composite)
            
            output_path = f"exports/batch_{batch_id}_clip_{clip_index}.mp4"
            
            success, result = create_reel_composite_video(
                reel_video_path=project.video_file_path,
                gameplay_video_path=selected_gameplay,
                output_path=output_path
            )
            
            if success:
                composite.status = "ready"
                composite.output_video_path = output_path
                batch.total_completed += 1
            else:
                composite.status = f"failed: {result}"
            
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

# --- ROUTES ---
@app.get("/")
def read_root():
    return {"message": "Welcome to Clipflow Instagram API v2", "version": "2.0.0"}

@app.post("/api/instagram/process")
def process_instagram(req: InstagramReelRequest, background_tasks: BackgroundTasks):
    """
    Accepts an Instagram reel URL and starts processing it in the background.
    """
    if not req.url or "instagram.com" not in req.url:
        raise HTTPException(status_code=400, detail="Invalid Instagram URL")
    
    db = SessionLocal()
    new_project = InstagramProjectDB(reel_url=req.url)
    db.add(new_project)
    db.commit()
    db.refresh(new_project)
    db.close()

    background_tasks.add_task(process_instagram_reel, req.url, new_project.id)
    return {
        "message": "Processing started",
        "project_id": new_project.id,
        "status": "processing"
    }

@app.get("/api/instagram/projects/{project_id}")
def get_project_status(project_id: int):
    """
    Gets the status of an Instagram reel project.
    """
    db = SessionLocal()
    project = db.query(InstagramProjectDB).filter(InstagramProjectDB.id == project_id).first()
    db.close()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    return {
        "id": project.id,
        "reel_url": project.reel_url,
        "status": project.status,
        "video_file_path": project.video_file_path,
        "duration": project.duration
    }

@app.post("/api/instagram/composite/generate")
def request_composite_generation(req: CompositeVideoRequest, background_tasks: BackgroundTasks):
    """
    Generates a single composite MP4 video with reel at top and gameplay at bottom.
    Duration is automatically matched to the reel video.
    """
    db = SessionLocal()
    project = db.query(InstagramProjectDB).filter(InstagramProjectDB.id == req.project_id).first()
    
    if not project:
        db.close()
        raise HTTPException(status_code=404, detail="Project not found")
    
    if project.status != "ready":
        db.close()
        raise HTTPException(status_code=400, detail=f"Project not ready. Current status: {project.status}")
    
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
    
    new_composite = InstagramCompositeDB(
        project_id=req.project_id,
        gameplay_source=gameplay_source
    )
    db.add(new_composite)
    db.commit()
    db.refresh(new_composite)
    db.close()
    
    background_tasks.add_task(
        generate_composite_worker,
        new_composite.id,
        req.project_id,
        gameplay_source
    )
    
    return {
        "message": "Composite video queued for generation",
        "composite_id": new_composite.id,
        "status": "pending",
        "gameplay": gameplay_source
    }

@app.post("/api/instagram/composite/batch")
def request_batch_generation(req: BatchCompositeRequest, background_tasks: BackgroundTasks):
    """
    Generates multiple composite videos with optional gameplay rotation.
    If rotate_gameplay=True and multiple gameplay videos exist, each clip uses a different one.
    """
    db = SessionLocal()
    project = db.query(InstagramProjectDB).filter(InstagramProjectDB.id == req.project_id).first()
    
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
    
    new_batch = InstagramBatchDB(
        project_id=req.project_id,
        num_clips=req.num_clips
    )
    db.add(new_batch)
    db.commit()
    db.refresh(new_batch)
    db.close()
    
    background_tasks.add_task(
        generate_batch_composites,
        new_batch.id,
        req.project_id,
        req.num_clips,
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

@app.get("/api/instagram/composites/{composite_id}")
def get_composite_status(composite_id: int):
    """
    Gets the status of a composite video generation task.
    """
    db = SessionLocal()
    composite = db.query(InstagramCompositeDB).filter(InstagramCompositeDB.id == composite_id).first()
    db.close()
    
    if not composite:
        raise HTTPException(status_code=404, detail="Composite not found")
    
    return {
        "id": composite.id,
        "project_id": composite.project_id,
        "status": composite.status,
        "output_video_path": composite.output_video_path,
        "gameplay_source": composite.gameplay_source
    }

@app.get("/api/instagram/batches/{batch_id}")
def get_batch_status(batch_id: int):
    """
    Gets the status of a batch generation task.
    """
    db = SessionLocal()
    batch = db.query(InstagramBatchDB).filter(InstagramBatchDB.id == batch_id).first()
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

@app.get("/api/instagram/gameplay/available")
def list_available_gameplay():
    """
    Lists all available gameplay videos.
    """
    available = get_available_gameplay()
    return {
        "total": len(available),
        "gameplay_videos": available
    }

@app.get("/api/instagram/health")
def health_check():
    """
    Health check endpoint.
    """
    available_gameplay = get_available_gameplay()
    return {
        "status": "healthy",
        "service": "Clipflow Instagram API v2",
        "available_gameplay_count": len(available_gameplay)
    }
