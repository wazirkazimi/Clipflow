import os
import sys
import logging
from instagram_helper import fetch_instagram_reel
from ffmpeg_helper import create_reel_composite_video, create_vertical_crop_short, get_video_duration
import static_ffmpeg

# Configure logging
logging.basicConfig(level=logging.ERROR)
static_ffmpeg.add_paths()

GAMEPLAY_ASSETS = [
    ("Temple Run", "assets/gameplay/temple_run.mp4", "https://youtu.be/TuGv1WIyUK4"),
    ("Need for Speed Car", "assets/gameplay/nfs_car.mp4", "https://youtu.be/AJm-cwt0Ba8"),
    ("Minecraft Parkour", "assets/gameplay/minecraft_parkour.mp4", "https://youtu.be/u7kdVe8q5zs"),
    ("Ramp Car", "assets/gameplay/ramp_car.mp4", "https://youtu.be/GyO1MtLhyt0"),
    ("BGMI", "assets/gameplay/bgmi.mp4", "https://youtu.be/ZWUV6IjPaaY"),
]


def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def print_header():
    print("\033[95m" + "="*50)
    print("   CLIPFLOW INSTAGRAM CLI GENERATOR")
    print("="*50 + "\033[0m")


def gameplay_ready(path: str) -> bool:
    return os.path.exists(path) and os.path.getsize(path) > 5_000_000


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

    is_hindi = False
    if use_captions:
        is_hindi_input = input("\033[94m[?]\033[0m Is the speech in Hindi? [y/n] (default n): ").strip().lower()
        is_hindi = is_hindi_input == 'y'
    
    forced_lang = 'hi' if is_hindi else None

    gameplay_path = None
    try:
        if use_gameplay:
            print("\n\033[94m[?]\033[0m Select Gameplay Background:")
            for idx, (label, path, _) in enumerate(GAMEPLAY_ASSETS, start=1):
                print(f" {idx}. {label}")

            gameplay_choice = input(f" Choice [1-{len(GAMEPLAY_ASSETS)}] (default 1): ").strip()
            choice_index = int(gameplay_choice) - 1 if gameplay_choice.isdigit() and 1 <= int(gameplay_choice) <= len(GAMEPLAY_ASSETS) else 0
            gameplay_path = GAMEPLAY_ASSETS[choice_index][1]
            gameplay_url = GAMEPLAY_ASSETS[choice_index][2]

            if not gameplay_ready(gameplay_path):
                print(f"\n\033[93m[!] Downloading gameplay background...\033[0m")
                os.makedirs("assets/gameplay", exist_ok=True)
                import subprocess
                subprocess.run([
                    sys.executable, "-m", "yt_dlp", "--no-playlist",
                    "--js-runtimes", "node",
                    "--remote-components", "ejs:github",
                    "-o", gameplay_path,
                    gameplay_url
                ])

        print("\n\033[96m[1/2]\033[0m Fetching and Downloading Instagram Reel...")
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
                add_captions=use_captions,
                forced_language=forced_lang
            )
        else:
            duration = get_video_duration(main_video_path) or 30.0
            success, result = create_vertical_crop_short(
                main_video_path=main_video_path,
                output_path=output_path,
                start_time=0,
                duration=duration,
                add_captions=use_captions,
                forced_language=forced_lang
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
