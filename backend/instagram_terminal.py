import os
import sys
import logging
from instagram_helper import fetch_instagram_reel
from ffmpeg_helper import create_reel_composite_video, create_vertical_crop_short, get_video_duration
import static_ffmpeg

# Configure logging
logging.basicConfig(level=logging.ERROR)
static_ffmpeg.add_paths()

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def print_header():
    print("\033[95m" + "="*50)
    print("   CLIPFLOW INSTAGRAM CLI GENERATOR")
    print("="*50 + "\033[0m")

def run_instagram_cli():
    clear_screen()
    print_header()
    
    print("\n\033[94m[?]\033[0m Paste the Instagram Reel URL below:")
    reel_url = input(" -> ").strip()
    
    if not reel_url or "instagram.com" not in reel_url:
        print("\n\033[91m[-] Invalid Instagram URL.\033[0m")
        return

    use_gameplay = input("\033[94m[?]\033[0m Include gameplay background (Split-Screen)? [y/n] (default y): ").strip().lower()
    use_gameplay = use_gameplay != 'n'

    use_captions = input("\033[94m[?]\033[0m Add viral captions (word-highlighted)? [y/n] (default y): ").strip().lower()
    use_captions = use_captions != 'n'

    gameplay_path = "assets/gameplay/subway_surfer_loop.mp4"
    if use_gameplay:
        print("\n\033[94m[?]\033[0m Select Gameplay Background:")
        print(" 1. Subway Surfers")
        print(" 2. Minecraft Parkour")
        gameplay_choice = input(" Choice [1/2]: ").strip()
        
        if gameplay_choice == "2":
            gameplay_path = "assets/gameplay/mc_parkour.mp4"
        
        if not os.path.exists(gameplay_path) or os.path.getsize(gameplay_path) < 100000:
            print(f"\n\033[93m[!] Downloading gameplay background...\033[0m")
            os.makedirs("assets/gameplay", exist_ok=True)
            import subprocess
            target_url = "https://www.youtube.com/watch?v=vTfD20dbxho" 
            if gameplay_choice == "2": target_url = "https://www.youtube.com/watch?v=n_Dv47ToG0Y"
            subprocess.run(["yt-dlp", "--download-sections", "*00:00:00-00:03:00", "-f", "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best", "-o", gameplay_path, target_url])

    print("\n\033[96m[1/2]\033[0m Fetching and Downloading Instagram Reel...")
    try:
        reel_info = fetch_instagram_reel(reel_url, download_video=True, output_dir="downloads")
        if not reel_info or not reel_info.get('filepath'):
            print("\033[91m[-] Failed to extract video.\033[0m")
            return
            
        main_video_path = reel_info['filepath']
        output_dir = os.path.join("exports", "instagram")
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f"reels_{reel_info.get('id', 'clip')}.mp4")
        
        print("\n\033[96m[2/2]\033[0m Processing Video...")
        
        if use_gameplay:
            success, result = create_reel_composite_video(
                reel_video_path=main_video_path, 
                gameplay_video_path=gameplay_path, 
                output_path=output_path,
                add_captions=use_captions
            )
        else:
            duration = get_video_duration(main_video_path) or 30.0
            success, result = create_vertical_crop_short(
                main_video_path=main_video_path, 
                output_path=output_path, 
                start_time=0, 
                duration=duration,
                add_captions=use_captions
            )
        
        if success:
            print("\n" + "="*50)
            print(f"\033[92m[+] SUCCESS! Clip generated: {os.path.basename(output_path)}\033[0m")
            print("="*50)
        else:
            print(f"\n\033[91m[-] Error: {result}\033[0m")
            
    except Exception as e:
        print(f"\n\033[91m[-] Unexpected Error: {str(e)}\033[0m")

if __name__ == "__main__":
    try:
        run_instagram_cli()
    except KeyboardInterrupt:
        print("\n\n\033[93m[-] Operation cancelled.\033[0m")
        sys.exit(0)
