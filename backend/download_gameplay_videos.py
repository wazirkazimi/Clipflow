import yt_dlp
import os
import static_ffmpeg

static_ffmpeg.add_paths()

# Download gameplay videos for clips
GAMEPLAY_VIDEOS = {
    "temple_run": "https://youtu.be/TuGv1WIyUK4?si=bJmH2h2e1R2VgHJ7",
    "nfs_car": "https://youtu.be/AJm-cwt0Ba8?si=-DpoNZE_i-heVyRV",
    "minecraft_parkour": "https://youtu.be/u7kdVe8q5zs?si=MAQGYUs1FkMkROVn",
    "ramp_car": "https://youtu.be/GyO1MtLhyt0?si=p_YQP4vcnOk3Yu2_",
    "bgmi": "https://youtu.be/ZWUV6IjPaaY?si=eNxqvuW6UPGEBljH"
}

def gameplay_ready(path):
    return os.path.exists(path) and os.path.getsize(path) > 5_000_000


def download_gameplay_video(name, url, output_dir="assets/gameplay"):
    """
    Downloads a gameplay video from YouTube.
    Downloads the middle section (from 5 minutes onward) to avoid intro sequences.
    """
    os.makedirs(output_dir, exist_ok=True)
    output_path = f'{output_dir}/{name}.mp4'

    if gameplay_ready(output_path):
        size_mb = os.path.getsize(output_path) / (1024 * 1024)
        print(f"✓ {name}: Already exists ({size_mb:.1f} MB)")
        return output_path

    ydl_opts = {
        'quiet': False,
        'outtmpl': output_path,
        'format': 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best',
        'download_sections': ['*00:05:00-00:15:00'],
        'merge_output_format': 'mp4',
        'js_runtime': 'node',
        'remote_components': ['ejs:github'],
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print(f"Downloading {name}...")
            info = ydl.extract_info(url, download=True)
            output_path = f"{output_dir}/{name}.mp4"
            print(f"✓ {name} downloaded: {output_path}")
            return output_path
    except Exception as e:
        print(f"✗ Error downloading {name}: {e}")
        return None

def main():
    print("Downloading gameplay videos from YouTube...")
    print("=" * 60)
    
    downloaded = []
    for name, url in GAMEPLAY_VIDEOS.items():
        result = download_gameplay_video(name, url)
        if result:
            downloaded.append((name, result))
    
    print("\n" + "=" * 60)
    print(f"Download complete! {len(downloaded)}/{len(GAMEPLAY_VIDEOS)} videos ready")
    print("\nAvailable gameplay videos:")
    for name, path in downloaded:
        print(f"  - {name}: {path}")

if __name__ == "__main__":
    main()
