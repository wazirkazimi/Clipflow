import os
from youtube_helper import fetch_youtube_video_info
from ffmpeg_helper import create_split_screen_short
import static_ffmpeg

static_ffmpeg.add_paths()

def get_top_heatmap_moments(heatmap_data, count=10, min_distance=30.0):
    if not heatmap_data:
        return []
    
    # Sort by highest heat value
    sorted_points = sorted(heatmap_data, key=lambda x: x.get('value', 0), reverse=True)
    
    selected_times = []
    
    for point in sorted_points:
        start_time = point.get('start_time', 0)
        # Check distance from already selected times to avoid overlapping
        is_far_enough = all(abs(start_time - st) >= min_distance for st in selected_times)
        
        if is_far_enough:
            selected_times.append(start_time)
        
        if len(selected_times) >= count:
            break
            
    return selected_times

def run():
    print("=== STARTING BATCH CLIP GENERATOR ===")
    
    main_url = "https://youtu.be/TlOWA6pyD3g?si=FW6Dvfilnx-XD3KL"
    gameplay_url = "https://youtu.be/vTfD20dbxho?si=7HF0Up0Y72cP4LaW"

    os.makedirs('assets/gameplay', exist_ok=True)
    os.makedirs('exports', exist_ok=True)
    
    # 1. Get Gameplay Loop
    print("\n[1] Fetching Subway Surfer Gameplay (first 5 mins)...")
    gameplay_id = "vTfD20dbxho"
    gameplay_path = f"assets/gameplay/{gameplay_id}.mp4"
    if not os.path.exists(gameplay_path):
        import subprocess
        subprocess.run([
            "yt-dlp", "--download-sections", "*00:00:00-00:05:00",
            "-f", "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best",
            "-o", gameplay_path,
            gameplay_url
        ])
    
    if not os.path.exists(gameplay_path):
        print("Failed to download gameplay!")
        return
        
    print(f"Gameplay loop ready at {gameplay_path}")
    
    # 2. Get Main Video
    print("\n[2] Fetching Main Video & Heatmap...")
    main_info = fetch_youtube_video_info(main_url, download_video=True, output_dir="downloads")
    if not main_info or not main_info.get('filepath'):
        print("Failed to download main video!")
        return
    main_path = main_info['filepath']
    heatmap = main_info.get('heatmap') or []
    duration = main_info.get('duration', 0)
    
    print(f"Main video duration: {duration}s. Heatmap points: {len(heatmap)}")
    
    # 3. Determine top moments
    top_moments = get_top_heatmap_moments(heatmap, count=10, min_distance=30.0)
    
    # Fallback if no heatmap
    if not top_moments:
        print("No heatmap data available. Falling back to naive timestamps...")
        top_moments = [i * 30.0 for i in range(10) if i * 30.0 < duration - 30]
        
    print(f"\n[3] Found {len(top_moments)} best moments. Generating Clips...")
    
    for i, start_time in enumerate(top_moments):
        out_file = f"exports/best_clip_{i+1}_at_{int(start_time)}s.mp4"
        print(f"  -> Generating Clip {i+1} at {start_time}s...")
        success, res = create_split_screen_short(
            main_video_path=main_path,
            gameplay_video_path=gameplay_path,
            output_path=out_file,
            start_time=start_time,
            duration=30.0 # 30 second format
        )
        if success:
            print(f"     ✅ Saved: {out_file}")
        else:
            print(f"     ❌ Failed: {res}")

if __name__ == "__main__":
    run()
