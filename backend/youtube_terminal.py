import os
import sys
import logging
from youtube_helper import fetch_youtube_video_info
from ffmpeg_helper import create_split_screen_short, create_vertical_crop_short
import static_ffmpeg

# Configure logging
logging.basicConfig(level=logging.ERROR)
static_ffmpeg.add_paths()

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def print_header():
    print("\033[91m" + "="*50)
    print("   CLIPFLOW YOUTUBE CLI GENERATOR")
    print("="*50 + "\033[0m")

def get_top_heatmap_moments(heatmap_data, count=3, min_distance=60.0):
    if not heatmap_data:
        return []
    sorted_points = sorted(heatmap_data, key=lambda x: x.get('value', 0), reverse=True)
    selected_moments = []
    for point in sorted_points:
        start_time = point.get('start_time', 0)
        value = point.get('value', 0)
        is_far_enough = all(abs(start_time - m['start_time']) >= min_distance for m in selected_moments)
        if is_far_enough:
            selected_moments.append({'start_time': start_time, 'value': value})
        if len(selected_moments) >= count:
            break
    return selected_moments

def run_youtube_cli():
    clear_screen()
    print_header()
    
    video_url = input("\n\033[94m[?]\033[0m Paste YouTube Video URL: ").strip()
    if not video_url or "youtu" not in video_url:
        print("\033[91m[-] Invalid YouTube URL.\033[0m")
        return

    # User Settings
    num_clips_input = input("\n\033[94m[?]\033[0m How many clips to generate? [Max: 15] (default 3): ").strip()
    num_clips = int(num_clips_input) if num_clips_input.isdigit() else 3
    num_clips = min(num_clips, 15)

    duration_input = input("\033[94m[?]\033[0m Enter clip duration in seconds [Max: 60s] (default 30): ").strip()
    clip_duration = float(duration_input) if duration_input.replace('.','',1).isdigit() else 30.0
    clip_duration = min(clip_duration, 60.0)

    use_gameplay = input("\033[94m[?]\033[0m Include gameplay background (Split-Screen)? [y/n] (default y): ").strip().lower()
    use_gameplay = use_gameplay != 'n' # Default to true unless 'n'

    use_captions = input("\033[94m[?]\033[0m Add viral captions (word-highlighted)? [y/n] (default y): ").strip().lower()
    use_captions = use_captions != 'n'

    is_hindi = False
    if use_captions:
        is_hindi_input = input("\033[94m[?]\033[0m Is the speech in Hindi? [y/n] (default n): ").strip().lower()
        is_hindi = is_hindi_input == 'y'

    forced_lang = 'hi' if is_hindi else None

    gameplay_path = "assets/gameplay/subway_surfer_loop.mp4"
    if use_gameplay:
        print("\n\033[94m[?]\033[0m Select Gameplay Background:")
        print(" 1. Subway Surfers")
        print(" 2. Minecraft Parkour")
        gameplay_choice = input(" Choice [1/2]: ").strip()
        
        gameplay_url = "https://www.youtube.com/watch?v=vTfD20dbxho"
        if gameplay_choice == "2":
            gameplay_path = "assets/gameplay/mc_parkour.mp4"
            gameplay_url = "https://www.youtube.com/watch?v=n_Dv47ToG0Y"

        # Ensure gameplay asset
        if not os.path.exists(gameplay_path) or os.path.getsize(gameplay_path) < 100000:
            print(f"\033[93m[!] Downloading gameplay background...\033[0m")
            os.makedirs("assets/gameplay", exist_ok=True)
            import subprocess
            subprocess.run([
                "yt-dlp", "--download-sections", "*00:00:00-00:05:00",
                "-f", "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best",
                "-o", gameplay_path,
                gameplay_url
            ])

    print("\n\033[96m[1/3]\033[0m Fetching Video Info & Heatmap...")
    main_info = fetch_youtube_video_info(video_url, download_video=False) # Always skip full download now
    
    if not main_info or not main_info.get('video_url'):
        print("\033[91m[-] Failed to extract video stream URLs.\033[0m")
        return
        
    main_path = main_info['video_url']
    audio_path = main_info.get('audio_url')
    heatmap = main_info.get('heatmap') or []
    total_duration = main_info.get('duration', 0)
    
    print(f"\033[92m[+]\033[0m Video duration: {int(total_duration)}s. Finding best moments...")
    
    top_moments = get_top_heatmap_moments(heatmap, count=num_clips, min_distance=clip_duration + 10)
    if not top_moments:
        print("\033[93m[!] No heatmap data. Using default intervals.\033[0m")
        top_moments = [{'start_time': i * (clip_duration + 60), 'value': 0} for i in range(num_clips) if i * (clip_duration + 60) < total_duration - clip_duration]

    output_dir = os.path.join("exports", "youtube")
    os.makedirs(output_dir, exist_ok=True)

    print(f"\n\033[96m[2/3]\033[0m Generating {len(top_moments)} clips (Parallel Processing)...")
    
    from concurrent.futures import ThreadPoolExecutor
    
    def process_single_moment(args):
        i, moment = args
        start_time = moment['start_time']
        rating = round(moment['value'] * 100, 1) if 'value' in moment else 0
        
        filename = f"clip_{i+1}_rating_{rating}_at_{int(start_time)}s.mp4"
        out_file = os.path.join(output_dir, filename)
        
        print(f"      -> Starting Clip {i+1} [Rating: {rating}] at {int(start_time)}s...")
        
        if use_gameplay:
            success, res = create_split_screen_short(
                main_video_path=main_path,
                gameplay_video_path=gameplay_path,
                output_path=out_file,
                start_time=start_time,
                duration=clip_duration,
                main_audio_path=audio_path,
                add_captions=use_captions,
                forced_language=forced_lang
            )
        else:
            success, res = create_vertical_crop_short(
                main_video_path=main_path,
                output_path=out_file,
                start_time=start_time,
                duration=clip_duration,
                main_audio_path=audio_path,
                add_captions=use_captions,
                forced_language=forced_lang
            )
            
        if success:
            print(f"         \033[92m✅ Saved: {filename}\033[0m")
        else:
            print(f"         \033[91m❌ Failed: {res}\033[0m")
        return success

    # Use 2-3 parallel workers to speed up but not freeze the PC
    with ThreadPoolExecutor(max_workers=3) as executor:
        list(executor.map(process_single_moment, enumerate(top_moments)))

    print("\n" + "="*50)
    print(f"\033[92m[+] SUCCESS! Batch generation complete.\033[0m")
    print(f"\033[94m[+] Clips directory: \033[0m{os.path.abspath(output_dir)}")
    print("="*50)

if __name__ == "__main__":
    try:
        run_youtube_cli()
    except KeyboardInterrupt:
        print("\n\n\033[93m[-] Operation cancelled by user.\033[0m")
        sys.exit(0)
